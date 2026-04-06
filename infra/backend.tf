terraform {
  backend "s3" {
    bucket = "phenom-development-tfstate"
    key    = "osint-nest-ops/terraform.tfstate"
    region = "us-east-1"
  }
}
