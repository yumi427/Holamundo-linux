resource "aws_internet_gateway" "puerta" {
  vpc_id = aws_vpc.pyme2.id
  tags   = { Name = "pyme-igw-tf" }
}

resource "aws_route_table" "publica" {
  vpc_id = aws_vpc.pyme2.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.puerta.id
  }
  tags = { Name = "rt-publica-tf" }
}

resource "aws_route_table_association" "web" {
  subnet_id      = aws_subnet.area["web"].id
  route_table_id = aws_route_table.publica.id
}