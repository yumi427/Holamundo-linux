# =====================================================================
#  PARTE 3 · clase 15 · LOS OJOS DE LA TIENDA (observabilidad con CloudWatch)
#  También lo aplica el PIPELINE: llega por pull request, como todo lo demás.
#
#  logs     → /aws/lambda/tienda-cicd (lo crea Lambda; el pipeline le pone 7 días de vida)
#  métricas → las de Lambda y API Gateway (gratis) + TiendaLaura (Pedidos, Ventas, Demora)
#  trazas   → X-Ray: la Lambda las manda (tracing_config en main.tf) y la página las lee
#  alarmas  → "tienda-cicd-se-cayo" y "tienda-cicd-lenta", que avisan por correo (SNS)
#  tablero  → el dashboard "tienda-cicd-laura": todo en una sola pantalla
# =====================================================================

variable "correo" {
  description = "Tu correo para las alarmas. En el pipeline sale del secreto CORREO del repositorio (Settings → Secrets and variables → Actions)"
  type        = string
  default     = "" # vacío = las alarmas suenan, pero no le escriben a nadie
}

locals {
  funcion = aws_lambda_function.back.function_name
  api     = aws_apigatewayv2_api.api.id
  logs    = "/aws/lambda/${aws_lambda_function.back.function_name}" # el grupo de logs que crea Lambda
}

# ======================= LA LAMBDA PUEDE MANDAR Y LEER TRAZAS ==========
# 1 · Mandar sus trazas a X-Ray, y leer las de las pruebas y el estado de las alarmas
#     (eso es lo que muestra la sección "Pruebas de observabilidad" de la página)
resource "aws_iam_role_policy" "observar" {
  name = "trazas-y-alarmas"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "MandarTrazas", Effect = "Allow", Action = ["xray:PutTraceSegments", "xray:PutTelemetryRecords"], Resource = "*" },
      { Sid = "LeerTrazas", Effect = "Allow", Action = ["xray:GetTraceSummaries", "xray:BatchGetTraces"], Resource = "*" },
      { Sid = "VerAlarmas", Effect = "Allow", Action = ["cloudwatch:DescribeAlarms"], Resource = "*" },
    ]
  })
}

# ======================= EL MEGÁFONO: SNS ==============================
# 2 · Un tema de SNS: lo que se publique ahí le llega a todos los suscritos
resource "aws_sns_topic" "alertas" {
  name = "tienda-cicd-alertas"
}

# 3 · Tu correo suscrito al tema (AWS te manda un correo para confirmar)
resource "aws_sns_topic_subscription" "correo" {
  count     = var.correo == "" ? 0 : 1
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.correo
}

# ======================= LAS ALARMAS ===================================
# 4 · Se cayó: la Lambda tuvo 1 error o más en el último minuto
resource "aws_cloudwatch_metric_alarm" "se_cayo" {
  alarm_name          = "tienda-cicd-se-cayo"
  alarm_description   = "La Lambda de la tienda está fallando: hay pedidos que no se cobran"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = local.funcion }
  statistic           = "Sum"
  period              = 60 # cada minuto
  evaluation_periods  = 1  # basta 1 minuto malo
  comparison_operator = "GreaterThanOrEqualToThreshold"
  threshold           = 1
  treat_missing_data  = "notBreaching"              # sin pedidos no hay errores: eso NO es una alarma
  alarm_actions       = [aws_sns_topic.alertas.arn] # pasa a ALARM → te escribe
  ok_actions          = [aws_sns_topic.alertas.arn] # vuelve a OK → también te avisa
}

# 5 · Está lenta: el 10 % más lento de los pedidos (p90) tarda más de 2 segundos.
#     Mide la Demora de los PEDIDOS (métrica propia), no la de toda la Lambda: así las
#     consultas rápidas de la página no esconden a los clientes que esperaron.
resource "aws_cloudwatch_metric_alarm" "lenta" {
  alarm_name          = "tienda-cicd-lenta"
  alarm_description   = "La tienda está lenta: el p90 de los pedidos pasó de 2 segundos"
  namespace           = "TiendaLaura"
  metric_name         = "Demora"
  dimensions          = { Tienda = "laura" }
  extended_statistic  = "p90" # percentil 90, no el promedio
  period              = 60
  evaluation_periods  = 1
  comparison_operator = "GreaterThanThreshold"
  threshold           = 2000 # milisegundos
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alertas.arn]
  ok_actions          = [aws_sns_topic.alertas.arn]
}

# ======================= LAS PREGUNTAS GUARDADAS =======================
# 6 · Consultas de Logs Insights listas para usar (Logs Insights → Consultas guardadas)
resource "aws_cloudwatch_query_definition" "ultimos" {
  name            = "tienda-cicd/ultimos-pedidos"
  log_group_names = [local.logs]
  query_string    = <<-EOT
    fields @timestamp, cliente, producto, talla, total, ms, traza
    | filter evento = "pedido"
    | sort @timestamp desc
    | limit 20
  EOT
}

resource "aws_cloudwatch_query_definition" "ventas" {
  name            = "tienda-cicd/ventas-por-producto"
  log_group_names = [local.logs]
  query_string    = <<-EOT
    filter evento = "pedido"
    | stats count(*) as pedidos, sum(total) as ventas by producto
    | sort ventas desc
  EOT
}

resource "aws_cloudwatch_query_definition" "errores" {
  name            = "tienda-cicd/errores"
  log_group_names = [local.logs]
  query_string    = <<-EOT
    fields @timestamp, @message
    | filter @message like /ERROR|Task timed out|rechazado/
    | sort @timestamp desc
    | limit 20
  EOT
}

# ======================= EL TABLERO ====================================
# 7 · Un dashboard con lo que Laura quiere ver de un vistazo
resource "aws_cloudwatch_dashboard" "tienda" {
  dashboard_name = "tienda-cicd-laura"
  dashboard_body = jsonencode({
    widgets = [
      {
        type       = "text", x = 0, y = 0, width = 24, height = 2
        properties = { markdown = "# 🛍️ Tienda de Laura · sala de control\nVentas, pedidos, errores y lentitud en una sola pantalla. Lo publica el pipeline, como todo lo demás." }
      },
      {
        type       = "alarm", x = 0, y = 2, width = 24, height = 2
        properties = { title = "¿Todo bien?", alarms = [aws_cloudwatch_metric_alarm.se_cayo.arn, aws_cloudwatch_metric_alarm.lenta.arn] }
      },
      {
        type = "metric", x = 0, y = 4, width = 12, height = 6
        properties = {
          title   = "💰 Ventas en pesos (por minuto)", region = "us-east-1", view = "timeSeries", stacked = true, stat = "Sum", period = 60
          metrics = [for p in ["camiseta", "gorra", "buzo"] : ["TiendaLaura", "Ventas", "Producto", p]]
        }
      },
      {
        type = "metric", x = 12, y = 4, width = 12, height = 6
        properties = {
          title   = "🧾 Pedidos por producto", region = "us-east-1", view = "timeSeries", stacked = true, stat = "Sum", period = 60
          metrics = [for p in ["camiseta", "gorra", "buzo"] : ["TiendaLaura", "Pedidos", "Producto", p]]
        }
      },
      {
        type = "metric", x = 0, y = 10, width = 8, height = 6
        properties = {
          title = "⚡ Lambda: invocaciones y errores", region = "us-east-1", view = "timeSeries", stat = "Sum", period = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", local.funcion],
            ["AWS/Lambda", "Errors", "FunctionName", local.funcion, { color = "#d62728" }],
          ]
        }
      },
      {
        type = "metric", x = 8, y = 10, width = 8, height = 6
        properties = {
          title = "🐢 Pedidos: cuánto tardan (ms)", region = "us-east-1", view = "timeSeries", period = 60
          metrics = [
            ["TiendaLaura", "Demora", "Tienda", "laura", { stat = "p50", label = "p50 (la mitad)" }],
            ["TiendaLaura", "Demora", "Tienda", "laura", { stat = "p90", label = "p90" }],
            ["TiendaLaura", "Demora", "Tienda", "laura", { stat = "Maximum", label = "el peor" }],
          ]
          annotations = { horizontal = [{ label = "alarma tienda-cicd-lenta", value = 2000 }] }
        }
      },
      {
        type = "metric", x = 16, y = 10, width = 8, height = 6
        properties = {
          title = "🚪 API Gateway: peticiones y errores", region = "us-east-1", view = "timeSeries", stat = "Sum", period = 60
          metrics = [
            ["AWS/ApiGateway", "Count", "ApiId", local.api],
            ["AWS/ApiGateway", "4xx", "ApiId", local.api, { color = "#ff7f0e" }],
            ["AWS/ApiGateway", "5xx", "ApiId", local.api, { color = "#d62728" }],
          ]
        }
      },
      {
        type = "log", x = 0, y = 16, width = 24, height = 6
        properties = {
          title = "📜 Últimos pedidos (Logs Insights)", region = "us-east-1", view = "table"
          query = "SOURCE '${local.logs}' | fields @timestamp, cliente, producto, talla, total, ms, traza | filter evento = \"pedido\" | sort @timestamp desc | limit 20"
        }
      },
    ]
  })
}

# ======================= LO QUE TE MUESTRA AL TERMINAR ================
output "tu_tablero" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/${aws_cloudwatch_dashboard.tienda.dashboard_name}"
}

output "tus_trazas" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#xray:service-map/map"
}
