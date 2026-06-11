# -----------------------------------------------------------------------------
# EFS — Persistent storage for Postgres data
# -----------------------------------------------------------------------------

resource "aws_efs_file_system" "nest_postgres" {
  encrypted = true

  lifecycle_policy {
    transition_to_ia = "AFTER_14_DAYS"
  }

  tags = merge(local.tags, {
    Name = "${local.project_name}-${local.service_name}-postgres"
  })
}

resource "aws_efs_mount_target" "nest" {
  count = length(data.aws_subnets.private.ids)

  file_system_id  = aws_efs_file_system.nest_postgres.id
  subnet_id       = tolist(data.aws_subnets.private.ids)[count.index]
  security_groups = [aws_security_group.nest.id]
}
