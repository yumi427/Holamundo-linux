data "aws_ssm_parameter" "amazon_linux" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_instance" "web" {
  ami                    = data.aws_ssm_parameter.amazon_linux.value
  instance_type          = var.tipo_instancia
  subnet_id              = aws_subnet.area["web"].id
  vpc_security_group_ids = [aws_security_group.web.id]
  key_name               = "Linux1"

  user_data = join("\n", [
    "#!/bin/bash",
    "dnf install -y nginx",
    "echo '<h1>Hola desde Terraform &#128640;</h1><p>Esta red y este servidor nacieron de un archivo de codigo.</p>' > /usr/share/nginx/html/index.html",
    "systemctl enable --now nginx",
  ])

  tags = { Name = "web-tf" }
}

output "tu_web" {
  value = "http://${aws_instance.web.public_ip}"
}