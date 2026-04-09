# -----------------------------------------------------------------------------
# ECS — Task definition and service for N.E.S.T. Ops
# Phase 1: Ghost Mode only. Additional containers added incrementally.
# -----------------------------------------------------------------------------

resource "aws_ecs_task_definition" "nest" {
  family                   = "${local.project_name}-${local.service_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.nest_task_execution.arn
  task_role_arn            = aws_iam_role.nest_task.arn

  container_definitions = jsonencode([
    {
      name      = "ghost-mode"
      image     = var.ghostmode_image
      essential = true

      portMappings = [
        {
          containerPort = 3200
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "NEST_MODE", value = "true" },
        { name = "MCP_PORT", value = "3200" },
        { name = "MCP_HOST", value = "0.0.0.0" },
        { name = "GHOSTMODE_FORMAT", value = "json" },
        { name = "DB_HOST", value = "phenom-dev-postgres.c8toq6uq223c.us-east-1.rds.amazonaws.com" },
        { name = "DB_PORT", value = "5432" },
        { name = "DB_USER", value = "nestops" },
        { name = "DB_NAME", value = "nestops" },
        { name = "ALERT_MODE", value = "ntfy" }
      ]

      secrets = [
        {
          name      = "CF_AUTH_EMAIL"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:cf_auth_email::"
        },
        {
          name      = "CF_AUTH_KEY"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:cf_auth_key::"
        },
        {
          name      = "DB_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:postgres_password::"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request; urllib.request.urlopen('http://localhost:3200/health')\" || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 5
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ghost-mode"
        }
      }
    }
  ])

  tags = local.tags
}

# -----------------------------------------------------------------------------
# ECS Service
# -----------------------------------------------------------------------------

resource "aws_ecs_service" "nest" {
  name             = "${local.project_name}-${local.service_name}"
  cluster          = data.aws_ecs_cluster.phenom.arn
  task_definition  = aws_ecs_task_definition.nest.arn
  desired_count    = 1
  launch_type      = "FARGATE"
  platform_version = "1.4.0"

  network_configuration {
    subnets          = data.aws_subnets.private.ids
    security_groups  = [aws_security_group.nest.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.nest.arn
    container_name   = "ghost-mode"
    container_port   = 3200
  }

  depends_on = [
    aws_lb_listener_rule.nest
  ]

  tags = local.tags
}
