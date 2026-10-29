# La tienda de Laura con ojos: observabilidad con CloudWatch

Laboratorio de la clase 15 · Esumer · Cloud Computing, Redes y Ciberseguridad.

Es la tienda serverless de la clase 12 (S3 + CloudFront + API Gateway + Lambda + DynamoDB),
ahora con **ojos**: logs en JSON, métricas propias de ventas, dos alarmas que te escriben al
correo y un tablero que lo junta todo.

```
tienda-laura-observa/
├── front/                ← la página (S3 + CloudFront): ahora con botones para provocar fallas
├── back/
│   └── app.py            ← la Lambda: cada pedido deja un log en JSON y las métricas Pedidos y Ventas
└── terraform/
    ├── main.tf           ← la tienda (como en la clase 12) + su grupo de logs
    └── observabilidad.tf ← SNS (correo) + 2 alarmas + 3 consultas guardadas + el tablero
```

Los nombres empiezan por `tienda-observa`, así que no chocan con la tienda de la clase 12.

## Antes de empezar (una sola vez)

Tu usuario `terraform-lab` ya tiene lo de la clase 12 (`AWSLambda_FullAccess`,
`AmazonAPIGatewayAdministrator` y la política insertada `solo-roles-tienda`). Hoy le faltan
CloudWatch y SNS. En IAM → Usuarios → terraform-lab → Agregar permisos → Adjuntar políticas
directamente:

1. `CloudWatchFullAccessV2`
2. `AmazonSNSFullAccess`

Si no hiciste la clase 12, agrega también las dos de arriba y la política insertada con el
contenido de `politica-iam-roles.json` (nombre `solo-roles-tienda`).

## PASO 1 · Pon la tienda en marcha

En la terminal de VS Code, **dentro de la carpeta `terraform`**, con **tu correo**:

```powershell
cd terraform
terraform init
terraform apply -var="correo=tu@correo.com"   # yes · unos 4 minutos (CloudFront)
```

Al terminar te muestra `tu_tienda`, `tu_api`, `tu_tablero` y `tus_alarmas`.

📬 **Abre tu correo**: llega *AWS Notification - Subscription Confirmation*. Pulsa
**Confirm subscription**. Sin eso, las alarmas suenan pero no te llega nada.

## PASO 2 · Los logs en vivo

Abre `tu_tienda` y haz 2 o 3 pedidos. En la terminal:

```powershell
aws logs tail /aws/lambda/tienda-observa --follow --format short
```

Por cada pedido ves:

- `START` y `END`: empezó y terminó una invocación.
- Tu log en JSON: `{"evento": "pedido", "cliente": "camila", "total": 59000, ...}`.
- La línea de métricas (`"_aws": ...`): de ahí salen Pedidos y Ventas.
- `REPORT`: `Duration`, `Billed Duration`, `Max Memory Used` y, si fue en frío, `Init Duration`.

`Ctrl + C` para salir.

## PASO 3 · Pregúntale a los logs (Logs Insights)

Consola → CloudWatch → Logs → **Logs Insights** → *Consultas guardadas* → `tienda/ventas-por-producto` → **Ejecutar consulta**.

```
filter evento = "pedido"
| stats count(*) as pedidos, sum(total) as ventas by producto
| sort ventas desc
```

Prueba también `tienda/ultimos-pedidos`. Como el log es JSON, cada campo (`cliente`,
`producto`, `total`, `ms`) es una columna.

## PASO 4 · El tablero

Abre `tu_tablero` (CloudWatch → Paneles → `tienda-laura`). Pulsa en la tienda
**⚡ Ráfaga: 20 pedidos a la vez** dos o tres veces y espera 1 o 2 minutos (las métricas llegan
por minuto). Mira:

- 💰 Ventas y 🧾 Pedidos: **tus** métricas (namespace `TiendaLaura`).
- ⚡ Invocaciones de la Lambda y 🚪 peticiones del API: las de AWS, gratis.
- 📜 Los últimos pedidos, salidos de los logs.

## PASO 5 · Rómpela: la alarma tienda-se-cayo

En la tienda, pulsa **💥 Simular falla (5 pedidos de «caos»)**: la Lambda lanza un error.

1. La tienda muestra `Internal Server Error`.
2. En 1 a 3 minutos, la alarma `tienda-se-cayo` pasa de **OK** a **En alarma**.
3. 📬 Te llega el correo *ALARM: "tienda-se-cayo"*.
4. Logs Insights → `tienda/errores`: ahí está el `[ERROR] RuntimeError: se cayó el cobro…`.
5. Sin más errores, a los minutos vuelve a **OK** y te llega otro correo.

## PASO 6 · Lenta no es caída: la alarma tienda-lenta

Pulsa **🐢 Pedidos lentos (5 de «lento»)**: cada uno tarda 3 segundos, pero todos se guardan.

- En 🐢 *Lambda: cuánto tarda*, el **p90** se dispara por encima de la línea de 2.000 ms.
- `tienda-lenta` pasa a **En alarma** y te escribe. `tienda-se-cayo` sigue en **OK**: no hubo errores.

El promedio esconde a los clientes que esperaron; el p90 dice cuánto esperó el 10 % peor atendido.

## PASO 7 · La alarma de la plata (AWS Budgets)

Con tu usuario de la consola (el que ve la facturación): **Billing and Cost Management →
Presupuestos → Crear un presupuesto** → *Usar una plantilla* → **Presupuesto mensual de
costos** → monto `5` USD → tu correo → **Crear presupuesto**.

AWS te escribe cuando el gasto real pase del 85 % y del 100 %, y cuando el pronóstico pase
del 100 %. Este se puede quedar: los dos primeros presupuestos son gratis.

## PASO 8 · Al terminar (¡importante!)

```powershell
terraform destroy -var="correo=tu@correo.com"   # yes · Destroy complete!
```

Se borra todo, también los logs (los creó Terraform). Las métricas no se borran: CloudWatch
las deja vencer solas y no cobran si nadie las envía.

## Lo que cuesta

Casi nada, y para el lab entra en la capa gratuita: 10 alarmas, 3 tableros, 5 GB de logs y
1 millón de peticiones a SNS al mes. Lo único fuera de ella son las 6 métricas propias
(Pedidos y Ventas por 3 productos): unos USD 0,30 al mes cada una, cobrados por hora.
Unas horas de lab cuestan menos de un centavo.
