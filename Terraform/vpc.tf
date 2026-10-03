resource "aws_vpc" "pyme2" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  tags                 = { Name = "pyme-vpc-tf" }
}