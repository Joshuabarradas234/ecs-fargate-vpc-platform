#############################################
# variables.tf
# All inputs. No hardcoded values in resources.
#############################################

variable "aws_region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "eu-west-2" # London
}

variable "project_name" {
  description = "Project name, used in resource names and tags."
  type        = string
  default     = "ecs-fargate-vpc-platform"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)."
  type        = string
  default     = "dev"
}

# ---------------------------------------------------------------------------
# Networking
# ---------------------------------------------------------------------------
variable "vpc_cidr" {
  description = "CIDR block for the VPC."
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for the two public subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]

  validation {
    condition     = length(var.public_subnet_cidrs) == 2
    error_message = "Exactly two public subnet CIDRs are required (one per AZ)."
  }
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for the two private subnets (one per AZ)."
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]

  validation {
    condition     = length(var.private_subnet_cidrs) == 2
    error_message = "Exactly two private subnet CIDRs are required (one per AZ)."
  }
}

# ---------------------------------------------------------------------------
# Application / container
# ---------------------------------------------------------------------------
variable "container_port" {
  description = "Port the application container listens on."
  type        = number
  default     = 8000
}

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
variable "db_name" {
  description = "Initial database name created in RDS."
  type        = string
  default     = "appdb"
}

variable "db_username" {
  description = "Master username for the RDS PostgreSQL instance."
  type        = string
  default     = "appuser"
}

variable "db_engine_version" {
  description = "PostgreSQL engine version."
  type        = string
  default     = "16.9"
}

variable "db_instance_class" {
  description = "RDS instance class. db.t3.micro keeps cost low for a demo."
  type        = string
  default     = "db.t3.micro"
}

variable "db_multi_az" {
  description = "Whether to run RDS Multi-AZ. False for cost; true for HA (~2x cost)."
  type        = bool
  default     = false
}

# ---------------------------------------------------------------------------
# Observability
# ---------------------------------------------------------------------------
variable "log_retention_days" {
  description = "CloudWatch log group retention in days."
  type        = number
  default     = 14
}
