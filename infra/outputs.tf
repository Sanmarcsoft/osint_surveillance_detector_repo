# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------

output "nest_url" {
  description = "URL for the N.E.S.T. Ops dashboard"
  value       = "https://${local.fqdn}"
}

output "cognito_client_id" {
  description = "Cognito user pool client ID for N.E.S.T. Ops"
  value       = aws_cognito_user_pool_client.nest.id
}

output "ecs_service_name" {
  description = "ECS service name for N.E.S.T. Ops"
  value       = aws_ecs_service.nest.name
}

output "target_group_arn" {
  description = "ALB target group ARN for N.E.S.T. Ops"
  value       = aws_lb_target_group.nest.arn
}

output "efs_file_system_id" {
  description = "EFS file system ID for Postgres data"
  value       = aws_efs_file_system.nest_postgres.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.nest.name
}
