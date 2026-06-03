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

# -----------------------------------------------------------------------------
# Cross-stack note (NOT managed here): the threat-map/surveillance board needs
# the task to reach phenom-dev-postgres:5432. That ingress lives on the RDS SG
# (phenom-dev-rds-sg / sg-096237355ca24cef6), allowing this task SG
# (aws_security_group.nest / sg-09b140ac78ed01af4) on 5432 — added out-of-band as
# rule sgr-0abd3fb. The RDS SG belongs to the database stack, so an apply here
# does NOT touch it; the DB stack owner should codify that ingress for durability.
# -----------------------------------------------------------------------------
