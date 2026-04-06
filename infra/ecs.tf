# -----------------------------------------------------------------------------
# ECS — Task definition and service for N.E.S.T. Ops (7 containers)
# -----------------------------------------------------------------------------

resource "aws_ecs_task_definition" "nest" {
  family                   = "${local.project_name}-${local.service_name}"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "2048"
  memory                   = "4096"
  execution_role_arn       = aws_iam_role.nest_task_execution.arn
  task_role_arn            = aws_iam_role.nest_task.arn

  volume {
    name = "postgres-data"

    efs_volume_configuration {
      file_system_id = aws_efs_file_system.nest_postgres.id
    }
  }

  container_definitions = jsonencode([
    # ---- nginx (port 80 — entry point) ----
    {
      name      = "nginx"
      image     = "nginx:alpine"
      essential = true

      portMappings = [
        {
          containerPort = 80
          protocol      = "tcp"
        }
      ]

      command = [
        "/bin/sh", "-c",
        "echo '${base64encode(templatefile("${path.module}/nginx.conf.tftpl", {}))}' | base64 -d > /etc/nginx/nginx.conf && nginx -g 'daemon off;'"
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://localhost:80/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      dependsOn = [
        {
          containerName = "ghost-mode"
          condition     = "HEALTHY"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "nginx"
        }
      }
    },

    # ---- ghost-mode (port 3200) ----
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
        { name = "PORT", value = "3200" }
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
          name      = "LINEAR_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:linear_api_key::"
        },
        {
          name      = "GITHUB_ORG_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:github_org_token::"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "wget -qO- http://localhost:3200/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ghost-mode"
        }
      }
    },

    # ---- grafana (port 3000) ----
    {
      name      = "grafana"
      image     = "grafana/grafana:latest"
      essential = false

      portMappings = [
        {
          containerPort = 3000
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "GF_SERVER_ROOT_URL", value = "https://${local.fqdn}/grafana/" },
        { name = "GF_SERVER_SERVE_FROM_SUB_PATH", value = "true" },
        { name = "GF_AUTH_PROXY_ENABLED", value = "true" },
        { name = "GF_AUTH_PROXY_HEADER_NAME", value = "X-Amzn-Oidc-Identity" },
        { name = "GF_AUTH_PROXY_HEADER_PROPERTY", value = "email" },
        { name = "GF_AUTH_PROXY_AUTO_SIGN_UP", value = "true" },
        { name = "GF_AUTH_DISABLE_LOGIN_FORM", value = "true" },
        { name = "GF_PANELS_DISABLE_SANITIZE_HTML", value = "true" }
      ]

      secrets = [
        {
          name      = "GF_SECURITY_ADMIN_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:grafana_admin_password::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "grafana"
        }
      }
    },

    # ---- prometheus (port 9090) ----
    {
      name      = "prometheus"
      image     = "prom/prometheus:latest"
      essential = false

      portMappings = [
        {
          containerPort = 9090
          protocol      = "tcp"
        }
      ]

      command = [
        "/bin/sh", "-c",
        join("", [
          "echo '${base64encode(yamlencode({
            global = {
              scrape_interval     = "15s"
              evaluation_interval = "15s"
            }
            scrape_configs = [
              {
                job_name        = "ghost-mode"
                metrics_path    = "/metrics"
                scrape_interval = "15s"
                static_configs  = [{ targets = ["127.0.0.1:3200"] }]
              },
              {
                job_name        = "blackbox"
                metrics_path    = "/metrics"
                scrape_interval = "30s"
                static_configs  = [{ targets = ["127.0.0.1:9115"] }]
              },
              {
                job_name        = "grafana"
                metrics_path    = "/grafana/metrics"
                scrape_interval = "30s"
                static_configs  = [{ targets = ["127.0.0.1:3000"] }]
              }
            ]
          }))}' | base64 -d > /tmp/prometheus.yml && ",
          "/bin/prometheus ",
          "--config.file=/tmp/prometheus.yml ",
          "--storage.tsdb.path=/prometheus ",
          "--storage.tsdb.retention.time=7d ",
          "--web.console.libraries=/usr/share/prometheus/console_libraries ",
          "--web.console.templates=/usr/share/prometheus/consoles"
        ])
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "prometheus"
        }
      }
    },

    # ---- blackbox exporter (port 9115) ----
    {
      name      = "blackbox"
      image     = "prom/blackbox-exporter:latest"
      essential = false

      portMappings = [
        {
          containerPort = 9115
          protocol      = "tcp"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "blackbox"
        }
      }
    },

    # ---- umami (port 3001) ----
    {
      name      = "umami"
      image     = "ghcr.io/umami-software/umami:postgresql-latest"
      essential = false

      portMappings = [
        {
          containerPort = 3001
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "BASE_PATH", value = "/umami" },
        { name = "PORT", value = "3001" }
      ]

      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:umami_database_url::"
        }
      ]

      dependsOn = [
        {
          containerName = "postgres"
          condition     = "HEALTHY"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "umami"
        }
      }
    },

    # ---- postgres (port 5432) ----
    {
      name      = "postgres"
      image     = "postgres:16-alpine"
      essential = true

      portMappings = [
        {
          containerPort = 5432
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "POSTGRES_DB", value = "umami" },
        { name = "POSTGRES_USER", value = "umami" }
      ]

      secrets = [
        {
          name      = "POSTGRES_PASSWORD"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:postgres_password::"
        }
      ]

      mountPoints = [
        {
          sourceVolume  = "postgres-data"
          containerPath = "/var/lib/postgresql/data"
          readOnly      = false
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "pg_isready -U umami -d umami"]
        interval    = 10
        timeout     = 5
        retries     = 5
        startPeriod = 30
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.nest.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "postgres"
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
    container_name   = "nginx"
    container_port   = 80
  }

  depends_on = [
    aws_lb_listener_rule.nest
  ]

  tags = local.tags
}
