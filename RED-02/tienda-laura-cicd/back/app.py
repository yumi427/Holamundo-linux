# =====================================================================
#  BACK de la tienda de Laura: una función Lambda en Python
#  Recibe los pedidos que manda el FRONT (por API Gateway), aplica las
#  reglas del negocio (productos, tallas y precios) y los guarda en DynamoDB.
#
#  PARTE 3 · clase 15 · los OJOS de la tienda:
#    logs     → cada pedido deja una línea en JSON (se puede preguntar con Logs Insights)
#    métricas → Pedidos y Ventas por producto (formato EMF: salen del mismo log)
#    trazas   → X-Ray: el recorrido de cada pedido, tramo por tramo (validar → DynamoDB → cobrar)
#  Y una puerta para mirar: GET /?observar=<prueba> devuelve las trazas de una prueba
#  y el estado de las alarmas (es lo que usa la sección "Pruebas de observabilidad" de la página).
# =====================================================================
import base64, json, os, re, time, uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import boto3
from boto3.dynamodb.conditions import Key

# El SDK de X-Ray lo empaqueta el pipeline junto a app.py (back/requirements.txt).
# Sin él (o fuera de Lambda, como en las pruebas) la tienda funciona igual, solo que sin tramos.
try:
    from aws_xray_sdk.core import patch, xray_recorder

    patch(["botocore"])  # cada llamada de boto3 (DynamoDB) sale como un tramo de la traza
    TRAZAS = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
except ImportError:
    TRAZAS = False

# Esto corre UNA sola vez, cuando AWS prende una instancia nueva (arranque en frío)
tabla = boto3.resource("dynamodb").Table(os.environ["TABLA"])
INSTANCIA = uuid.uuid4().hex[:6]  # nombre corto de esta instancia de la Lambda
frio = True

# Reglas del negocio: viven en el BACK, nunca en el front (allá cualquiera las cambia con F12)
PRECIOS = {"camiseta": 59000, "gorra": 39000, "buzo": 119000}
TALLAS = {"S", "M", "L", "XL"}

FUNCION = os.environ.get("AWS_LAMBDA_FUNCTION_NAME", "tienda-cicd")
PRUEBA_VALIDA = re.compile(r"^[a-z0-9-]{4,40}$")  # el nombre de una prueba: letras, números y guiones


def responder(codigo, datos):
    return {"statusCode": codigo, "headers": {"content-type": "application/json"}, "body": json.dumps(datos, default=str)}


# ---------------------------------------------------------------- LOS OJOS
def traza_actual():
    """El número de la traza de ESTA petición: Lambda lo deja en una variable de entorno."""
    cabecera = os.environ.get("_X_AMZN_TRACE_ID", "")  # Root=1-6720…;Parent=…;Sampled=1
    partes = dict(p.split("=", 1) for p in cabecera.split(";") if "=" in p)
    return partes.get("Root", ""), partes.get("Sampled") == "1"


def log(evento, **datos):
    """Un log en JSON: cada campo es una columna en Logs Insights."""
    print(json.dumps({"evento": evento, "traza": traza_actual()[0], **datos}, default=str))


def metricas(producto, total, ms):
    """Métricas propias con EMF: CloudWatch lee esta línea del log y la vuelve métrica.
    Pedidos y Ventas van por producto; Demora (cuánto tardó el pedido) va para toda la tienda."""
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [
                {"Namespace": "TiendaLaura", "Dimensions": [["Producto"]],
                 "Metrics": [{"Name": "Pedidos", "Unit": "Count"}, {"Name": "Ventas", "Unit": "None"}]},
                {"Namespace": "TiendaLaura", "Dimensions": [["Tienda"]],
                 "Metrics": [{"Name": "Demora", "Unit": "Milliseconds"}]},
            ],
        },
        "Producto": producto,
        "Tienda": "laura",
        "Pedidos": 1,
        "Ventas": total,
        "Demora": ms,
    }))


@contextmanager
def tramo(nombre, **marcas):
    """Un tramo de la traza (subsegmento de X-Ray). Las marcas son anotaciones: se pueden buscar."""
    if not TRAZAS:
        yield
        return
    with xray_recorder.in_subsegment(nombre) as sub:
        for clave, valor in marcas.items():
            sub.put_annotation(clave, valor)
        yield


def cobrar(cliente, total):
    """La pasarela de pagos (de mentiras). Dos clientes especiales para practicar:
    "caos" → la pasarela no responde (error) · "lento" → la pasarela tarda 3 segundos."""
    with tramo("cobrar"):
        if cliente == "caos":
            raise RuntimeError("se cayó el cobro: la pasarela de pagos no respondió")
        time.sleep(3 if cliente == "lento" else 0.05)


# ---------------------------------------------------------------- MIRAR DESDE LA PÁGINA
def tramos_de(documentos):
    """Una traza llega por partes (varios documentos): los armamos como un árbol, cada tramo
    debajo de su padre, y lo volvemos una lista en orden (padre, hijos, nietos…)."""
    nodos = {}

    def indexar(n):
        nodos[n.get("id")] = n
        for sub in n.get("subsegments") or []:
            indexar(sub)

    for d in documentos:
        indexar(d)
    hijos, raices = {}, []
    for d in documentos:  # un documento cuelga de otro tramo si su parent_id existe en la traza
        padre = d.get("parent_id")
        (hijos.setdefault(padre, []) if padre in nodos and padre != d.get("id") else raices).append(d)

    salida = []
    inicio = lambda n: n.get("start_time") or 0

    def visitar(n, nivel):
        salida.append({
            "nombre": n.get("name"),
            "origen": n.get("origin"),  # AWS::Lambda (el servicio), AWS::Lambda::Function (tu código)…
            "operacion": (n.get("aws") or {}).get("operation"),
            "inicio": n.get("start_time"),
            "fin": n.get("end_time") or n.get("start_time"),
            "nivel": nivel,
            "falla": bool(n.get("fault") or n.get("error")),
        })
        for h in sorted(list(n.get("subsegments") or []) + hijos.get(n.get("id"), []), key=inicio):
            visitar(h, nivel + 1)

    for r in sorted(raices, key=inicio):
        visitar(r, 0)
    return salida


def observar(prueba):
    """Las trazas de UNA prueba (buscadas por su anotación) y cómo están las alarmas."""
    xray = boto3.client("xray")
    ahora = datetime.now(timezone.utc)
    resumen = xray.get_trace_summaries(
        StartTime=ahora - timedelta(minutes=20), EndTime=ahora,
        FilterExpression=f'annotation.prueba = "{prueba}"',
    )["TraceSummaries"]
    trazas = []
    detalle = xray.batch_get_traces(TraceIds=[t["Id"] for t in resumen[:5]])["Traces"] if resumen else []
    for t in detalle:
        tramos = tramos_de([json.loads(seg["Document"]) for seg in t["Segments"]])
        base = min((x["inicio"] for x in tramos if x["inicio"]), default=0)
        for x in tramos:
            x["desde_ms"] = round(((x.pop("inicio") or base) - base) * 1000)
            x["ms"] = max(0, round(((x.pop("fin") or base) - base) * 1000) - x["desde_ms"])
        s = next(r for r in resumen if r["Id"] == t["Id"])
        trazas.append({
            "id": t["Id"], "ms": round((s.get("Duration") or 0) * 1000),
            "falla": s.get("HasFault", False), "error": s.get("HasError", False),
            "tramos": tramos[:30],
        })
    alarmas = boto3.client("cloudwatch").describe_alarms(AlarmNamePrefix="tienda-cicd-")["MetricAlarms"]
    return {
        "prueba": prueba,
        "trazas": trazas,
        "alarmas": [{"nombre": a["AlarmName"], "estado": a["StateValue"]} for a in alarmas],
    }


# ---------------------------------------------------------------- LA TIENDA
def handler(event, context):
    # Esto corre en CADA petición
    global frio
    inicio = time.time()
    era_frio, frio = frio, False
    metodo = event["requestContext"]["http"]["method"]
    consulta = event.get("queryStringParameters") or {}

    if metodo == "GET" and "observar" in consulta:  # la página pregunta por una prueba
        prueba = str(consulta["observar"]).strip().lower()
        if not PRUEBA_VALIDA.match(prueba):
            return responder(400, {"error": "esa prueba no tiene un nombre válido"})
        return responder(200, observar(prueba))

    if metodo == "POST":  # guardar un pedido
        cuerpo = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            cuerpo = base64.b64decode(cuerpo).decode()
        datos = json.loads(cuerpo)
        cliente = str(datos.get("cliente", "")).strip().lower()[:40]
        producto = str(datos.get("producto", "")).strip().lower()
        talla = str(datos.get("talla", "M")).strip().upper()
        prueba = str(datos.get("prueba", "")).strip().lower()
        try:
            cantidad = max(1, min(5, int(datos.get("cantidad", 1))))
        except (TypeError, ValueError):
            cantidad = 1
        marcas = {"cliente": cliente or "-", "producto": producto or "-"}
        if PRUEBA_VALIDA.match(prueba):
            marcas["prueba"] = prueba  # así la página encuentra la traza de su prueba

        with tramo("pedido", **marcas):
            with tramo("validar"):
                problema = None
                if not cliente:
                    problema = "falta el nombre del cliente"
                elif producto not in PRECIOS:
                    problema = "ese producto no existe"
                elif talla not in TALLAS:
                    problema = "esa talla no existe"
            if problema:
                log("rechazado", motivo=problema, cliente=cliente, producto=producto, talla=talla)
                traza, muestreada = traza_actual()
                return responder(400, {"error": problema, "traza": traza, "muestreada": muestreada})
            pedido = {
                "cliente": cliente,  # llave de partición
                # llave de orden: la hora + 4 letras al azar (dos pedidos en el mismo milisegundo no se pisan)
                "fecha": datetime.now(timezone.utc).isoformat(timespec="milliseconds") + "#" + uuid.uuid4().hex[:4],
                "producto": producto,
                "talla": talla,
                "cantidad": cantidad,
                "total": PRECIOS[producto] * cantidad,  # el precio lo pone el back
                "instancia": INSTANCIA,
            }
            tabla.put_item(Item=pedido)  # PutItem: guardar (en la traza sale como el tramo DynamoDB)
            cobrar(cliente, pedido["total"])  # caos → error · lento → 3 segundos
        ms = round((time.time() - inicio) * 1000)
        log("pedido", cliente=cliente, producto=producto, talla=talla, cantidad=cantidad, total=pedido["total"], ms=ms)
        metricas(producto, pedido["total"], ms)
        resultado = {"operacion": "PutItem", "pedido": pedido}
    else:
        # GET: ?cliente=camila → Query (solo su partición) · sin cliente → Scan (toda la tabla)
        cliente = (consulta.get("cliente") or "").strip().lower()
        if cliente:
            items = tabla.query(KeyConditionExpression=Key("cliente").eq(cliente))["Items"]
            resultado = {"operacion": "Query", "pedidos": items}
        else:
            items = tabla.scan()["Items"]
            resultado = {"operacion": "Scan", "pedidos": items}
        resultado["pedidos"].sort(key=lambda p: p["fecha"], reverse=True)

    traza, muestreada = traza_actual()
    resultado.update({
        "instancia": INSTANCIA, "frio": era_frio, "ms": round((time.time() - inicio) * 1000),
        "traza": traza, "muestreada": muestreada, "funcion": FUNCION,
    })
    return responder(200, resultado)
