# =====================================================================
#  BACK de la tienda de Laura: una función Lambda en Python
#  Recibe los pedidos que manda el FRONT (por API Gateway), aplica las
#  reglas del negocio (productos, tallas y precios) y los guarda en DynamoDB.
#
#  Clase 15 · observabilidad: cada pedido deja en CloudWatch
#    1. un LOG en JSON (para buscarlo con Logs Insights)
#    2. dos MÉTRICAS propias: Pedidos y Ventas (en pesos), por producto
# =====================================================================
import base64, json, os, time, uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key

# Esto corre UNA sola vez, cuando AWS prende una instancia nueva (arranque en frío)
tabla = boto3.resource("dynamodb").Table(os.environ["TABLA"])
INSTANCIA = uuid.uuid4().hex[:6]  # nombre corto de esta instancia de la Lambda
frio = True

# Reglas del negocio: viven en el BACK, nunca en el front (allá cualquiera las cambia con F12)
PRECIOS = {"camiseta": 59000, "gorra": 39000, "buzo": 119000}
TALLAS = {"S", "M", "L", "XL"}


def log(evento, **datos):
    # Un log ESTRUCTURADO: una línea de JSON con campos fijos.
    # Logs Insights los lee como columnas: fields cliente, total | filter evento = "pedido"
    print(json.dumps({"evento": evento, "instancia": INSTANCIA, **datos}, default=str))


def metricas(producto, total):
    # Formato EMF (Embedded Metric Format): un log con la llave "_aws".
    # CloudWatch lo lee y crea las métricas solo: no hay que llamar a ninguna API.
    print(json.dumps({
        "_aws": {
            "Timestamp": int(time.time() * 1000),
            "CloudWatchMetrics": [{
                "Namespace": "TiendaLaura",
                "Dimensions": [["Producto"]],
                "Metrics": [{"Name": "Pedidos", "Unit": "Count"}, {"Name": "Ventas", "Unit": "None"}],
            }],
        },
        "Producto": producto,
        "Pedidos": 1,
        "Ventas": total,
    }))


def responder(codigo, datos):
    return {"statusCode": codigo, "headers": {"content-type": "application/json"}, "body": json.dumps(datos, default=str)}


def handler(event, context):
    # Esto corre en CADA petición
    global frio
    inicio = time.time()
    era_frio, frio = frio, False
    metodo = event["requestContext"]["http"]["method"]

    if metodo == "POST":  # guardar un pedido
        cuerpo = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            cuerpo = base64.b64decode(cuerpo).decode()
        datos = json.loads(cuerpo)
        cliente = str(datos.get("cliente", "")).strip().lower()[:40]
        producto = str(datos.get("producto", "")).strip().lower()
        talla = str(datos.get("talla", "M")).strip().upper()
        try:
            cantidad = max(1, min(5, int(datos.get("cantidad", 1))))
        except (TypeError, ValueError):
            cantidad = 1

        # ---- LAB: dos clientes "especiales" para ver fallas en CloudWatch ----
        if cliente == "caos":
            # un error de verdad: la Lambda se cae → métrica Errors +1 → API responde 500
            raise RuntimeError("se cayó el cobro: la pasarela de pagos no respondió")
        if cliente == "lento":
            time.sleep(3)  # la pasarela demora 3 segundos → sube la métrica Duration

        if not cliente:
            log("rechazado", motivo="falta el nombre del cliente")
            return responder(400, {"error": "falta el nombre del cliente"})
        if producto not in PRECIOS:
            log("rechazado", motivo="ese producto no existe", producto=producto)
            return responder(400, {"error": "ese producto no existe"})
        if talla not in TALLAS:
            log("rechazado", motivo="esa talla no existe", talla=talla)
            return responder(400, {"error": "esa talla no existe"})
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
        tabla.put_item(Item=pedido)  # PutItem: guardar
        ms = round((time.time() - inicio) * 1000)
        log("pedido", cliente=cliente, producto=producto, talla=talla, cantidad=cantidad, total=pedido["total"], frio=era_frio, ms=ms)
        metricas(producto, pedido["total"])
        resultado = {"operacion": "PutItem", "pedido": pedido}
    else:
        # GET: ?cliente=camila → Query (solo su partición) · sin cliente → Scan (toda la tabla)
        cliente = ((event.get("queryStringParameters") or {}).get("cliente") or "").strip().lower()
        if cliente:
            items = tabla.query(KeyConditionExpression=Key("cliente").eq(cliente))["Items"]
            resultado = {"operacion": "Query", "pedidos": items}
        else:
            items = tabla.scan()["Items"]
            resultado = {"operacion": "Scan", "pedidos": items}
        resultado["pedidos"].sort(key=lambda p: p["fecha"], reverse=True)

    resultado.update({"instancia": INSTANCIA, "frio": era_frio, "ms": round((time.time() - inicio) * 1000)})
    return responder(200, resultado)
