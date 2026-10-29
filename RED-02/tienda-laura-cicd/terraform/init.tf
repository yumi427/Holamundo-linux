terraform {
  required_version = ">= 1.10" # use_lockfile (el candado en S3) llegó en la 1.10
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 6.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.0" }
  }

  # EL ESTADO REMOTO: un solo estado para el pipeline y para todo el equipo
  backend "s3" {
    # bucket = lo trae backend.hcl (lo escribió bootstrap con TU número de cuenta)
    key          = "tienda/terraform.tfstate" # el archivo del estado dentro del bucket
    region       = "us-east-1"
    encrypt      = true # cifrado en S3
    use_lockfile = true # el candado: terraform.tfstate.tflock mientras alguien aplica
  }
}

provider "aws" {
  region = "us-east-1"
}