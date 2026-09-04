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

# osint #85: the shared phenom ECS task SG. phenom-dev-rds-sg grants 5432 to
# exactly this group ("PostgreSQL from ECS tasks"), so a task must be a member
# to reach Postgres. nest-ops rolled its own SG and therefore never inherited
# that grant: every event-store connection timed out, and the threat map served
# an empty result for every window past 23h. Attaching this alongside the
# nest SG is the pattern every other phenom service already follows, and it
# keeps the grant inside a SG this stack does not own and cannot regress.
data "aws_security_group" "ecs_tasks" {
  name   = "phenom-dev-ecs-tasks-sg"
  vpc_id = data.aws_vpc.phenom.id
}

# Cognito pool is now a required variable (var.cognito_user_pool_id) — the
# old aws_cognito_user_pools name-match ("phem dev - 1jvngd") was garbled and
# returned an empty list, poisoning every plan. See variables.tf.
