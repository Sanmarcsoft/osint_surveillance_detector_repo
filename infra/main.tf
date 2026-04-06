# -----------------------------------------------------------------------------
# Data Sources — reference existing phenom-infra resources
# -----------------------------------------------------------------------------

data "aws_region" "current" {}

data "aws_caller_identity" "current" {}

data "aws_vpc" "phenom" {
  tags = {
    Name = "phenom-dev-vpc"
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.phenom.id]
  }

  tags = {
    Type = "Private"
  }
}

data "aws_lb" "phenom" {
  name = "phenom-dev-alb"
}

data "aws_lb_listener" "https" {
  load_balancer_arn = data.aws_lb.phenom.arn
  port              = 443
}

data "aws_ecs_cluster" "phenom" {
  cluster_name = "phenom-dev-cluster"
}

data "aws_security_group" "alb" {
  tags = {
    Name = "phenom-dev-alb-sg"
  }
}

data "aws_cognito_user_pools" "phenom" {
  name = "phem dev - 1jvngd"
}
