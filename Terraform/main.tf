terraform {
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.0" }
  }
}

provider "aws" {
  region = "us-east-1"
}

variable "mi_ip" { type = string } # tu IP de casa con /32
variable "tipo_instancia" {
  type    = string
  default = "t3.micro"
}