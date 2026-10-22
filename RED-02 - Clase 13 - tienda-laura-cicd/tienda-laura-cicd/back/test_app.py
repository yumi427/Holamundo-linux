# =====================================================================
#  PRUEBAS del BACK: GitHub Actions las corre en CADA push.
#  Si una falla (❌), el pipeline se detiene y la tienda NO se publica:
#  los clientes siguen viendo la versión que sí funcionaba.
#
#  Para correrlas en tu PC (opcional):  python -m unittest discover -s back -v
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


if __name__ == "__main__":
    unittest.main()
