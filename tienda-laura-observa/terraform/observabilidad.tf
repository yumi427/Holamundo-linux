# =====================================================================
#  LOS OJOS DE LA TIENDA · clase 15 · observabilidad con CloudWatch
#
#  logs     → /aws/lambda/tienda-observa (en main.tf, retención de 1 día)
#  métricas → las de Lambda y API Gateway (gratis) + TiendaLaura (Pedidos, Ventas)
#  alarmas  → "tienda-se-cayo" y "tienda-lenta", que avisan por correo (SNS)
#  tablero  → el dashboard "tienda-laura": todo en una sola pantalla
# =====================================================================

variable "correo" {
  description = "Tu correo: ahí llegan las alarmas (confirma la suscripción que te manda AWS)"
  type        = string
}

locals {
  funcion = aws_lambda_function.back.function_name
  api     = aws_apigatewayv2_api.api.id
}

# ======================= EL MEGÁFONO: SNS ==============================
# 1 · Un tema de SNS: lo que se publique ahí le llega a todos los suscritos
resource "aws_sns_topic" "alertas" {
  name = "tienda-alertas"
}

# 2 · Tu correo suscrito al tema (AWS te manda un correo para confirmar)
resource "aws_sns_topic_subscription" "correo" {
  topic_arn = aws_sns_topic.alertas.arn
  protocol  = "email"
  endpoint  = var.correo
}

# ======================= LAS ALARMAS ===================================
# 3 · Se cayó: la Lambda tuvo 1 error o más en el último minuto
resource "aws_cloudwatch_metric_alarm" "se_cayo" {
  alarm_name          = "tienda-se-cayo"
  alarm_description   = "La Lambda de la tienda está fallando: hay pedidos que no se guardan"
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

# 4 · Está lenta: el 90 % de los pedidos (p90) tarda más de 2 segundos
resource "aws_cloudwatch_metric_alarm" "lenta" {
  alarm_name          = "tienda-lenta"
  alarm_description   = "La tienda está lenta: el p90 de la Lambda pasó de 2 segundos"
  namespace           = "AWS/Lambda"
  metric_name         = "Duration"
  dimensions          = { FunctionName = local.funcion }
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
# 5 · Consultas de Logs Insights listas para usar (Logs Insights → Consultas guardadas)
resource "aws_cloudwatch_query_definition" "ultimos" {
  name            = "tienda/ultimos-pedidos"
  log_group_names = [aws_cloudwatch_log_group.back.name]
  query_string    = <<-EOT
    fields @timestamp, cliente, producto, talla, total, ms
    | filter evento = "pedido"
    | sort @timestamp desc
    | limit 20
  EOT
}

resource "aws_cloudwatch_query_definition" "ventas" {
  name            = "tienda/ventas-por-producto"
  log_group_names = [aws_cloudwatch_log_group.back.name]
  query_string    = <<-EOT
    filter evento = "pedido"
    | stats count(*) as pedidos, sum(total) as ventas by producto
    | sort ventas desc
  EOT
}

resource "aws_cloudwatch_query_definition" "errores" {
  name            = "tienda/errores"
  log_group_names = [aws_cloudwatch_log_group.back.name]
  query_string    = <<-EOT
    fields @timestamp, @message
    | filter @message like /ERROR|Task timed out|rechazado/
    | sort @timestamp desc
    | limit 20
  EOT
}

# ======================= EL TABLERO ====================================
# 6 · Un dashboard con lo que Laura quiere ver de un vistazo
resource "aws_cloudwatch_dashboard" "tienda" {
  dashboard_name = "tienda-laura"
  dashboard_body = jsonencode({
    widgets = [
      {
        type       = "text", x = 0, y = 0, width = 24, height = 2
        properties = { markdown = "# 🛍️ Tienda de Laura · sala de control\nVentas, pedidos, errores y lentitud en una sola pantalla. Las alarmas avisan a **${var.correo}**." }
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
          title = "🐢 Lambda: cuánto tarda (ms)", region = "us-east-1", view = "timeSeries", period = 60
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", local.funcion, { stat = "p50", label = "p50 (la mitad)" }],
            ["AWS/Lambda", "Duration", "FunctionName", local.funcion, { stat = "p90", label = "p90" }],
            ["AWS/Lambda", "Duration", "FunctionName", local.funcion, { stat = "Maximum", label = "el peor" }],
          ]
          annotations = { horizontal = [{ label = "alarma tienda-lenta", value = 2000 }] }
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
          query = "SOURCE '${aws_cloudwatch_log_group.back.name}' | fields @timestamp, cliente, producto, talla, total, ms | filter evento = \"pedido\" | sort @timestamp desc | limit 20"
        }
      },
    ]
  })
}

# ======================= LO QUE TE MUESTRA AL TERMINAR ================
output "tu_tablero" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#dashboards/dashboard/${aws_cloudwatch_dashboard.tienda.dashboard_name}"
}

output "tus_alarmas" {
  value = "https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#alarmsV2:"
}
