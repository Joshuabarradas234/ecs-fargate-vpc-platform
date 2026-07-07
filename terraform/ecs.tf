#############################################
# ecs.tf
# ECR repository, ECS Fargate cluster, task definition
# (DB creds injected from Secrets Manager, awslogs -> CloudWatch),
# and the service running 2 tasks behind the ALB.
#############################################

# ---------------------------------------------------------------------------
# ECR repository for the app image (CI/CD pushes here).
# ---------------------------------------------------------------------------
resource "aws_ecr_repository" "app" {
  name                 = "${local.name_prefix}-app"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  # Portfolio/demo: allow the repo (and its images) to be removed on destroy.
  force_delete = true

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app" })
}

# ---------------------------------------------------------------------------
# CloudWatch log group for the ECS task (awslogs driver ships here).
# ---------------------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${local.name_prefix}"
  retention_in_days = var.log_retention_days
  tags              = local.common_tags
}

# ---------------------------------------------------------------------------
# ECS cluster (Fargate).
# ---------------------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "${local.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-cluster" })
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ---------------------------------------------------------------------------
# Task definition.
# DB credentials are injected as individual env vars from the Secrets Manager
# secret (never hardcoded). `secrets` pulls specific JSON keys by name.
# ---------------------------------------------------------------------------
resource "aws_ecs_task_definition" "app" {
  family                   = "${local.name_prefix}-app"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256" # smallest — keep cost low
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "app"
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = var.container_port
          protocol      = "tcp"
        }
      ]

      # Non-secret config.
      environment = [
        { name = "DB_PORT", value = "5432" },
        { name = "DB_NAME", value = var.db_name }
      ]

      # Secret config: each pulls one key out of the JSON secret.
      secrets = [
        {
          name      = "DB_HOST"
          valueFrom = "${aws_secretsmanager_secret.db.arn}:host::"
        },
        {
          name      = "DB_USER"
          valueFrom = "${aws_secretsmanager_secret.db.arn}:username::"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.db.arn}:password::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "app"
        }
      }
    }
  ])

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app" })
}

# ---------------------------------------------------------------------------
# ECS service: 2 tasks across the 2 private subnets, behind the ALB.
# ---------------------------------------------------------------------------
resource "aws_ecs_service" "app" {
  name            = "${local.name_prefix}-app"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.private[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false # tasks reach the internet via the NAT gateway
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  # Give tasks time to pass health checks before the ALB counts them.
  health_check_grace_period_seconds = 60

  # Ensure the listener exists before the service registers targets.
  depends_on = [aws_lb_listener.http]

  tags = merge(local.common_tags, { Name = "${local.name_prefix}-app" })
}
