#############################################
# rds.tf
# RDS PostgreSQL in private subnets, encrypted at rest,
# not publicly accessible, with credentials generated and
# stored in Secrets Manager (never hardcoded).
#############################################

# DB subnet group across the two private subnets.
resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-db-subnet-group" })
}

# ---------------------------------------------------------------------------
# Generated DB password (never committed, stored in Secrets Manager).
# ---------------------------------------------------------------------------
resource "random_password" "db" {
  length  = 24
  special = false # avoid chars that need escaping in connection strings
}

resource "aws_secretsmanager_secret" "db" {
  name        = "${local.name_prefix}-db-credentials"
  description = "RDS Postgres credentials for ${local.name_prefix}"
  tags        = local.common_tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    dbname   = var.db_name
    port     = 5432
    host     = aws_db_instance.main.address
  })
}

# ---------------------------------------------------------------------------
# KMS key for encryption at rest.
# ---------------------------------------------------------------------------
resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption (${local.name_prefix})"
  deletion_window_in_days = 7
  enable_key_rotation     = true
  tags                    = local.common_tags
}

resource "aws_kms_alias" "rds" {
  name          = "alias/${local.name_prefix}-rds"
  target_key_id = aws_kms_key.rds.key_id
}

# ---------------------------------------------------------------------------
# RDS instance.
# COST TRADE-OFF: single-AZ db.t3.micro keeps cost ~$15/mo. Multi-AZ is the
# production choice (automatic failover) but roughly doubles cost.
# Documented in README + DECISION_RECORD.
# ---------------------------------------------------------------------------
resource "aws_db_instance" "main" {
  identifier     = "${local.name_prefix}-db"
  engine         = "postgres"
  engine_version = var.db_engine_version
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = aws_kms_key.rds.arn

  db_name  = var.db_name
  username = var.db_username
  password = random_password.db.result
  port     = 5432

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.db_multi_az

  backup_retention_period = 7
  skip_final_snapshot     = true # portfolio/demo: allow clean teardown
  deletion_protection     = false

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-db" })
}
