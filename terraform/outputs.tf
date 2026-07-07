#############################################
# outputs.tf
# Values needed to verify the stack and drive CI/CD.
#############################################

output "alb_dns_name" {
  description = "Public DNS name of the ALB. curl http://<this>/health should return 200."
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL to push the app image to."
  value       = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name."
  value       = aws_ecs_cluster.main.name
}

output "ecs_service_name" {
  description = "ECS service name (used by deploy.yml to force new deployments)."
  value       = aws_ecs_service.app.name
}

output "rds_endpoint" {
  description = "RDS endpoint address (private — not publicly reachable)."
  value       = aws_db_instance.main.address
}

output "vpc_id" {
  description = "VPC ID."
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "Public subnet IDs (ALB, NAT)."
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (ECS tasks, RDS)."
  value       = aws_subnet.private[*].id
}

output "db_secret_arn" {
  description = "ARN of the Secrets Manager secret holding DB credentials."
  value       = aws_secretsmanager_secret.db.arn
}

output "alarms_sns_topic_arn" {
  description = "SNS topic ARN that CloudWatch alarms publish to."
  value       = aws_sns_topic.alarms.arn
}
