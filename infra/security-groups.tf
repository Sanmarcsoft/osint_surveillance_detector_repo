# -----------------------------------------------------------------------------
# Security Groups — ECS tasks for N.E.S.T. Ops
# -----------------------------------------------------------------------------

resource "aws_security_group" "nest" {
  name        = "${local.project_name}-${local.service_name}"
  description = "Security group for N.E.S.T. Ops ECS tasks"
  vpc_id      = data.aws_vpc.phenom.id

  # Allow inbound HTTP from the ALB security group
  ingress {
    description     = "HTTP from ALB"
    from_port       = 80
    to_port         = 80
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
