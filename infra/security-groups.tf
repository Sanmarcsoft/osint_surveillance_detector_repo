# -----------------------------------------------------------------------------
# Security Groups — ECS tasks for N.E.S.T. Ops
# -----------------------------------------------------------------------------

resource "aws_security_group" "nest" {
  name        = "${local.project_name}-${local.service_name}"
  description = "Security group for N.E.S.T. Ops ECS tasks"
  vpc_id      = data.aws_vpc.phenom.id

  # Allow the ALB to reach the Ghost Mode container on its serving port (3200 —
  # the task-def portMapping and target-group port). Config previously said 80,
  # which does not match the container and would have severed ALB->app on apply.
  ingress {
    description     = "Ghost Mode from ALB"
    from_port       = 3200
    to_port         = 3200
    protocol        = "tcp"
    security_groups = [data.aws_security_group.alb.id]
  }

  # Allow NFS/EFS traffic within this security group
  ingress {
    description = "NFS/EFS self"
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    self        = true
  }

  # Allow all outbound traffic
  egress {
    description = "All outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(local.tags, {
    Name = "${local.project_name}-${local.service_name}"
  })
}
