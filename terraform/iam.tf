#############################################
# iam.tf
# ECS task execution role (pull image, write logs, read the DB secret)
# and task role (app runtime permissions — minimal).
# Least-privilege: only the specific secret ARN is readable.
#############################################

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ---------------------------------------------------------------------------
# Execution role: used by the ECS agent to pull the image and ship logs.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_execution" {
  name               = "${local.name_prefix}-ecs-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.common_tags
}

# AWS-managed policy covers ECR pull + CloudWatch Logs create/put.
resource "aws_iam_role_policy_attachment" "ecs_execution_managed" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Allow the execution role to read ONLY this app's DB secret (and decrypt it).
resource "aws_iam_role_policy" "ecs_execution_secret" {
  name   = "${local.name_prefix}-read-db-secret"
  role   = aws_iam_role.ecs_execution.id
  policy = data.aws_iam_policy_document.read_db_secret.json
}

data "aws_iam_policy_document" "read_db_secret" {
  statement {
    sid       = "ReadDbSecret"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.db.arn]
  }

  statement {
    sid       = "DecryptWithRdsKey"
    effect    = "Allow"
    actions   = ["kms:Decrypt"]
    resources = [aws_kms_key.rds.arn]
  }
}

# ---------------------------------------------------------------------------
# Task role: the app's own runtime identity. Kept minimal — the app talks to
# RDS over the network, not via AWS APIs, so it needs almost nothing here.
# ---------------------------------------------------------------------------
resource "aws_iam_role" "ecs_task" {
  name               = "${local.name_prefix}-ecs-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
  tags               = local.common_tags
}
