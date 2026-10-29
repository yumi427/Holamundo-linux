# =====================================================================
#  PRUEBAS del BACK: GitHub Actions las corre en CADA push.
#  Si una falla (❌), el pipeline se detiene y la tienda NO se publica:
#  los clientes siguen viendo la versión que sí funcionaba.
#
#  Para correrlas en tu PC (opcional):  python -m unittest discover -s back -v
#  Parte 3: también revisan los OJOS (el log en JSON, las métricas, la falla y la lentitud)
# =====================================================================
import json
import os
import unittest

os.environ.setdefault("TABLA", "tabla-de-prueba")        # la Lambda espera esta variable
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")  # boto3 necesita una región

import app  # noqa: E402  (el archivo app.py de esta misma carpeta)


class TablaFalsa:
    """Hace de DynamoDB en las pruebas: guarda en una lista y no toca AWS."""

    def __init__(self):
        self.guardados = []

    def put_item(self, Item):
        self.guardados.append(Item)


class Salida(list):
    """Atrapa lo que la Lambda imprime (los logs) para revisarlo en las pruebas."""

    def __enter__(self):
        self._print, app.print = getattr(app, "print", print), lambda *a, **k: self.append(" ".join(map(str, a)))
        return self

    def __exit__(self, *errores):
        app.print = self._print


def pedido(**datos):
    """Arma el mismo evento que API Gateway le manda a la Lambda en un POST."""
    return {"requestContext": {"http": {"method": "POST"}}, "body": json.dumps(datos)}


class PruebasDeLaTienda(unittest.TestCase):
    def setUp(self):
        app.tabla = TablaFalsa()  # cambiamos la tabla real por la falsa

    def test_precios_oficiales(self):
        # Si alguien cambia un precio por error, esta prueba lo atrapa
        self.assertEqual(app.PRECIOS, {"camiseta": 59000, "gorra": 39000, "buzo": 119000})

    def test_el_total_lo_calcula_el_back(self):
        r = app.handler(pedido(cliente="camila", producto="camiseta", talla="M", cantidad=2), None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(json.loads(r["body"])["pedido"]["total"], 118000)
        self.assertEqual(len(app.tabla.guardados), 1)  # se guardó UNA vez

    def test_talla_que_no_existe(self):
        r = app.handler(pedido(cliente="camila", producto="gorra", talla="XXL"), None)
        self.assertEqual(r["statusCode"], 400)

    def test_producto_que_no_existe(self):
        r = app.handler(pedido(cliente="camila", producto="zapatos"), None)
        self.assertEqual(r["statusCode"], 400)

    def test_pedido_sin_nombre(self):
        r = app.handler(pedido(cliente="", producto="buzo"), None)
        self.assertEqual(r["statusCode"], 400)
        self.assertEqual(app.tabla.guardados, [])  # no guardó nada

    # ------------------------------------------------ PARTE 3 · los ojos de la tienda
    def test_cada_pedido_deja_un_log_en_json_y_sus_metricas(self):
        with Salida() as logs:
            app.handler(pedido(cliente="camila", producto="buzo", talla="L"), None)
        lineas = [json.loads(l) for l in logs]  # si una línea no es JSON, esta prueba falla
        log = next(l for l in lineas if l.get("evento") == "pedido")
        self.assertEqual((log["producto"], log["total"]), ("buzo", 119000))
        emf = next(l for l in lineas if "_aws" in l)  # la línea que CloudWatch vuelve métrica
        self.assertEqual(emf["_aws"]["CloudWatchMetrics"][0]["Namespace"], "TiendaLaura")
        self.assertEqual((emf["Producto"], emf["Ventas"]), ("buzo", 119000))
        self.assertIsInstance(emf["Demora"], int)  # de aquí sale la alarma tienda-cicd-lenta

    def test_un_pedido_malo_deja_log_de_rechazado(self):
        with Salida() as logs:
            app.handler(pedido(cliente="camila", producto="zapatos"), None)
        self.assertIn("rechazado", [json.loads(l).get("evento") for l in logs])

    def test_caos_hace_fallar_el_cobro(self):
        # el cliente "caos" simula que la pasarela de pagos se cae: la Lambda falla de verdad
        with Salida(), self.assertRaises(RuntimeError):
            app.handler(pedido(cliente="caos", producto="gorra"), None)

    def test_lento_tarda_tres_segundos_en_cobrar(self):
        esperas = []
        dormir, app.time.sleep = app.time.sleep, esperas.append  # no esperamos de verdad
        try:
            with Salida():
                r = app.handler(pedido(cliente="lento", producto="gorra"), None)
        finally:
            app.time.sleep = dormir
        self.assertEqual(r["statusCode"], 200)
        self.assertIn(3, esperas)

    def test_observar_solo_acepta_nombres_de_prueba_validos(self):
        r = app.handler({"requestContext": {"http": {"method": "GET"}}, "queryStringParameters": {"observar": 'x" OR 1=1'}}, None)
        self.assertEqual(r["statusCode"], 400)

    def test_la_respuesta_trae_el_numero_de_la_traza(self):
        os.environ["_X_AMZN_TRACE_ID"] = "Root=1-6720abcd-0123456789abcdef01234567;Parent=53995c3f42cd8ad8;Sampled=1"
        try:
            with Salida():
                cuerpo = json.loads(app.handler(pedido(cliente="camila", producto="gorra"), None)["body"])
        finally:
            del os.environ["_X_AMZN_TRACE_ID"]
        self.assertEqual(cuerpo["traza"], "1-6720abcd-0123456789abcdef01234567")
        self.assertTrue(cuerpo["muestreada"])

    def test_la_cascada_respeta_el_arbol_de_la_traza(self):
        # X-Ray manda la traza por partes: cada tramo debe quedar debajo de su padre
        funcion = {"id": "f", "parent_id": "s", "name": "tienda-cicd", "start_time": 2, "subsegments": [
            {"id": "p", "name": "pedido", "start_time": 1, "subsegments": [
                {"id": "d", "name": "DynamoDB", "start_time": 3}, {"id": "c", "name": "cobrar", "start_time": 4}]}]}
        tabla = {"id": "t", "parent_id": "d", "name": "DynamoDB", "origin": "AWS::DynamoDB::Table", "start_time": 3}
        servicio = {"id": "s", "name": "tienda-cicd", "origin": "AWS::Lambda", "start_time": 0}
        orden = [(x["nombre"], x["nivel"]) for x in app.tramos_de([tabla, funcion, servicio])]
        self.assertEqual(orden, [("tienda-cicd", 0), ("tienda-cicd", 1), ("pedido", 2), ("DynamoDB", 3), ("DynamoDB", 4), ("cobrar", 3)])


if __name__ == "__main__":
    unittest.main()
