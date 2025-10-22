terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "45sq-terraform-state-files"
    key            = "dynamodb/fantasy-player-data/terraform.tfstate"
    region         = "us-west-2"
    dynamodb_table = "terraform-state-lock"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.50"
    }
  }
}