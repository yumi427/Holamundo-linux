# =====================================================================
#  BOOTSTRAP · lo ÚNICO que corres a mano, una sola vez
#  Esumer · Cloud Computing, Redes y Ciberseguridad
#
#  El huevo y la gallina: el pipeline guarda el estado de Terraform en un
#  bucket S3… pero ese bucket tiene que existir ANTES del primer pipeline.
#  Aquí se crea, junto con la entrada sin llaves (OIDC) para GitHub:
#
#    1 · el bucket del ESTADO (con versiones y candado)
#    2 · el proveedor OIDC de GitHub
#    3 · el rol tienda-cicd-plan   → lo usa cada PULL REQUEST (solo mirar)
#    4 · el rol tienda-cicd-apply  → lo usa cada push a MAIN (aplicar)
#    5 · escribe ../terraform/backend.hcl y los dos pipelines:
#        ../.github/workflows/pipeline.yml  → clase 13: solo la infraestructura
#        ../parte2/pipeline.yml             → clase 14: infraestructura + aplicación
#
#  Uso (terminal de VS Code, DENTRO de esta carpeta bootstrap):
#    terraform init
#    terraform apply      (te pregunta tu repositorio de GitHub · menos de 1 minuto)
#  Su estado queda en ESTE PC (terraform.tfstate): no borres esta carpeta
#  hasta el final de la parte 2.
# =====================================================================

terraform {
  required_version = ">= 1.10" # use_lockfile (el candado en S3) llegó en la 1.10
  required_providers {
    aws   = { source = "hashicorp/aws", version = "~> 6.0" }
    local = { source = "hashicorp/local", version = "~> 2.0" }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ======================= TUS DATOS ====================================
variable "repo_github" {
  description = "Tu repositorio de GitHub como usuario/repositorio, copiado EXACTO de la URL (ejemplo: camila-perez/tienda-laura)"
  type        = string
  validation {
    condition     = can(regex("^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$", var.repo_github))
    error_message = "Escríbelo como usuario/repositorio, sin https://github.com/ (ejemplo: camila-perez/tienda-laura)."
  }
}

variable "carpeta" {
  description = "Solo si el lab NO está en la raíz de tu repositorio: la ruta de esta carpeta dentro del repo (ejemplo: labs/tienda-laura-cicd). Vacío = el lab es el repo."
  type        = string
  default     = ""
  validation {
    condition     = !strcontains(var.carpeta, "..")
    error_message = "Escribe la ruta desde la raíz del repositorio hacia abajo, sin '..' (ejemplo: labs/tienda-laura-cicd)."
  }
}

locals {
  carpeta = trim(replace(var.carpeta, "\\", "/"), "/")                        # acepta \ de Windows
  raiz    = local.carpeta == "" ? "." : local.carpeta                         # dónde corre el pipeline
  subir   = join("", [for p in split("/", local.carpeta) : "/.." if p != ""]) # de aquí a la raíz del repo
}

variable "crear_proveedor" {
  description = "true = crea el proveedor OIDC de GitHub en tu cuenta · false = ya existe (EntityAlreadyExists) y se reutiliza"
  type        = bool
  default     = true
}

data "aws_caller_identity" "yo" {}

locals {
  cuenta = data.aws_caller_identity.yo.account_id
  estado = "tienda-estado-${local.cuenta}" # el número de cuenta lo hace único en el mundo
}

# ======================= 1 · EL ESTADO ================================
# Un solo estado para todo el equipo (y para el pipeline)
resource "aws_s3_bucket" "estado" {
  bucket        = local.estado
  force_destroy = true # permite borrarlo aunque tenga archivos (solo para el lab)
}

# cada apply guarda una VERSIÓN nueva del estado: si algo se daña, se vuelve a la anterior
resource "aws_s3_bucket_versioning" "estado" {
  bucket = aws_s3_bucket.estado.id
  versioning_configuration {
    status = "Enabled"
  }
}

# el estado describe toda tu infraestructura: cifrado y nunca público
resource "aws_s3_bucket_server_side_encryption_configuration" "estado" {
  bucket = aws_s3_bucket.estado.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "estado" {
  bucket                  = aws_s3_bucket.estado.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ======================= 2 · OIDC: GitHub entra SIN llaves ============
resource "aws_iam_openid_connect_provider" "github" {
  count          = var.crear_proveedor ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}

data "aws_iam_openid_connect_provider" "github" {
  count = var.crear_proveedor ? 0 : 1
  url   = "https://token.actions.githubusercontent.com"
}

locals {
  proveedor_arn = var.crear_proveedor ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.github[0].arn

  # la política de confianza: SOLO tu repositorio y SOLO el evento que digas
  confianza = {
    for rol, sub in {
      plan  = "repo:${var.repo_github}:pull_request"        # un pull request
      apply = "repo:${var.repo_github}:ref:refs/heads/main" # un push a main
      } : rol => jsonencode({
        Version = "2012-10-17"
        Statement = [{
          Effect    = "Allow"
          Principal = { Federated = local.proveedor_arn }
          Action    = "sts:AssumeRoleWithWebIdentity"
          Condition = {
            StringEquals = { "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com" }
            StringLike   = { "token.actions.githubusercontent.com:sub" = sub }
          }
        }]
    })
  }
}

# ======================= 3 · EL ROL DEL PULL REQUEST: solo mirar ======
resource "aws_iam_role" "plan" {
  name               = "tienda-cicd-plan"
  assume_role_policy = local.confianza.plan
}

# leer TODO (para que terraform plan compare)… pero no cambiar nada
resource "aws_iam_role_policy_attachment" "plan_leer" {
  role       = aws_iam_role.plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

# lo único que escribe: el candado del estado (mientras corre el plan)
resource "aws_iam_role_policy" "plan_candado" {
  name = "solo-el-candado"
  role = aws_iam_role.plan.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid      = "PonerYQuitarElCandado"
      Effect   = "Allow"
      Action   = ["s3:PutObject", "s3:DeleteObject"]
      Resource = "${aws_s3_bucket.estado.arn}/tienda/terraform.tfstate.tflock"
    }]
  })
}

# ======================= 4 · EL ROL DE MAIN: aplicar la tienda ========
resource "aws_iam_role" "apply" {
  name               = "tienda-cicd-apply"
  assume_role_policy = local.confianza.apply
}

# SOLO los recursos de la tienda (todos se llaman tienda-cicd-…)
resource "aws_iam_role_policy" "apply" {
  name = "solo-la-tienda"
  role = aws_iam_role.apply.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Sid = "VerElEstado", Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.estado.arn },
      { Sid = "LeerYGuardarElEstado", Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"], Resource = "${aws_s3_bucket.estado.arn}/tienda/*" },
      { Sid = "LaTabla", Effect = "Allow", Action = ["dynamodb:*"], Resource = "arn:aws:dynamodb:*:${local.cuenta}:table/tienda-cicd-*" },
      { Sid = "LaLambda", Effect = "Allow", Action = ["lambda:*"], Resource = "arn:aws:lambda:*:${local.cuenta}:function:tienda-cicd*" },
      { Sid = "LaAPI", Effect = "Allow", Action = ["apigateway:*"], Resource = "arn:aws:apigateway:us-east-1::/*" },
      { Sid = "ElBucketDelFront", Effect = "Allow", Action = ["s3:*"], Resource = ["arn:aws:s3:::tienda-cicd-*", "arn:aws:s3:::tienda-cicd-*/*"] },
      { Sid = "CloudFront", Effect = "Allow", Action = ["cloudfront:*"], Resource = "*" },
      {
        Sid    = "ElRolDeLaLambda" # solo ESE rol: el pipeline no puede darse más permisos a sí mismo
        Effect = "Allow"
        Action = [
          "iam:CreateRole", "iam:DeleteRole", "iam:GetRole", "iam:TagRole", "iam:UntagRole", "iam:UpdateAssumeRolePolicy",
          "iam:PutRolePolicy", "iam:GetRolePolicy", "iam:DeleteRolePolicy", "iam:ListRolePolicies",
          "iam:ListAttachedRolePolicies", "iam:ListInstanceProfilesForRole"
        ]
        Resource = "arn:aws:iam::${local.cuenta}:role/tienda-cicd-lambda"
      },
      {
        Sid       = "SoloLaPoliticaDeLogs"
        Effect    = "Allow"
        Action    = ["iam:AttachRolePolicy", "iam:DetachRolePolicy"]
        Resource  = "arn:aws:iam::${local.cuenta}:role/tienda-cicd-lambda"
        Condition = { ArnEquals = { "iam:PolicyARN" = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" } }
      },
      {
        Sid       = "PasarleElRolALaLambda"
        Effect    = "Allow"
        Action    = ["iam:PassRole"]
        Resource  = "arn:aws:iam::${local.cuenta}:role/tienda-cicd-lambda"
        Condition = { StringEquals = { "iam:PassedToService" = "lambda.amazonaws.com" } }
      }
    ]
  })
}

# ======================= 5 · LOS ARCHIVOS PARA TU REPO ================
# dónde está el estado (lo lee terraform init, en el pipeline y en tu PC)
resource "local_file" "backend" {
  filename = "${path.module}/../terraform/backend.hcl"
  content  = "# Lo escribió bootstrap: el bucket donde vive el estado de la tienda\nbucket = \"${aws_s3_bucket.estado.id}\"\n"
}

# los dos pipelines con TUS dos roles
resource "local_file" "workflow" {                                            # clase 13: solo la infraestructura
  filename = "${path.module}/..${local.subir}/.github/workflows/pipeline.yml" # en la RAÍZ del repo
  content = templatefile("${path.module}/pipeline-1-infra.yml.tpl", {
    rol_plan  = aws_iam_role.plan.arn
    rol_apply = aws_iam_role.apply.arn
    carpeta   = local.carpeta
    raiz      = local.raiz
  })
}

resource "local_file" "workflow_app" { # clase 14: infraestructura + aplicación
  filename = "${path.module}/../parte2/pipeline.yml"
  content = templatefile("${path.module}/pipeline-2-app.yml.tpl", {
    rol_plan  = aws_iam_role.plan.arn
    rol_apply = aws_iam_role.apply.arn
    carpeta   = local.carpeta
    raiz      = local.raiz
  })
}

# ======================= LO QUE TE MUESTRA AL TERMINAR ================
output "bucket_del_estado" {
  value = aws_s3_bucket.estado.id
}

output "rol_plan" {
  value = aws_iam_role.plan.arn
}

output "rol_apply" {
  value = aws_iam_role.apply.arn
}

output "siguiente_paso" {
  value = "Listos terraform/backend.hcl, parte2/pipeline.yml y ${local.carpeta == "" ? "" : "(en la raíz del repo) "}.github/workflows/pipeline.yml → súbelo a https://github.com/${var.repo_github} (PASO 3)"
}
