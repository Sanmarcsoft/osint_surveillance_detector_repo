# -----------------------------------------------------------------------------
# CloudWatch — Log group for ECS task containers
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "nest" {
  name              = "/ecs/${local.project_name}-${local.service_name}"
  retention_in_days = 7

  tags = local.tags
}
