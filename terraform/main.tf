#############################################
# main.tf
# Provider, versions, common locals.
#############################################

terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
  }

  # Remote state is optional. To use it, create the bucket + DynamoDB table
  # first, then uncomment and fill in. The bucket must block public access.
  # backend "s3" {
  #   bucket         = "REPLACE_ME-tfstate"
  #   key            = "ecs-fargate-vpc-platform/terraform.tfstate"
  #   region         = "eu-west-2"
  #   dynamodb_table = "REPLACE_ME-tf-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Availability zones actually available in the chosen region.
data "aws_availability_zones" "available" {
  state = "available"
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  name_prefix = "${var.project_name}-${var.environment}"

  # Use the first two AZs in the region for the 2-AZ layout.
  azs = slice(data.aws_availability_zones.available.names, 0, 2)

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}
