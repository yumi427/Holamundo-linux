locals {
  subredes = {
    ventas = "10.0.1.0/26"
    admin  = "10.0.1.64/27"
    web    = "10.0.1.96/28"
    bd     = "10.0.1.112/28"
  }
}

resource "aws_subnet" "area" {
  for_each                = local.subredes
  vpc_id                  = aws_vpc.pyme2.id
  cidr_block              = each.value
  availability_zone       = "us-east-1a"
  map_public_ip_on_launch = each.key == "web"
  tags                    = { Name = "${each.key}-tf" }
}