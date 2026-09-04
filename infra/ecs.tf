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

      # Scaleway Container Registry requires auth (ECR is auto-authed via the
      # execution role and REJECTS repositoryCredentials). So attach pull creds
      # ONLY for non-ECR (Scaleway) images; omit the key entirely for ECR.
      repositoryCredentials = strcontains(var.ghostmode_image, "dkr.ecr") ? null : {
        credentialsParameter = aws_secretsmanager_secret.scaleway_pull.arn
      }

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
        { name = "ALERT_MODE", value = "ntfy" },
        # asset_monitor is a singleton pager gated on RUN_ASSET_MONITOR (default
        # off; see ghostmode/asset_monitor.py). The ECS nest-ops task is the ONE
        # designated pager, so it sets this true. Every other `ghostmode serve`
        # instance (e.g. crabkey, outside the AWS VPC) leaves it unset so the
        # monitor never starts — prevents the 2026-06-13 false-DOWN flood. (#65)
        { name = "RUN_ASSET_MONITOR", value = "true" },
        { name = "NTFY_SERVER", value = "https://alerts.sanmarcsoft.com" },
        { name = "NTFY_TOPIC", value = "ghostmode-alerts" },
        { name = "NTFY_USER", value = "ghostmode-publisher" },
        # osint #22: pin the expected JWT signer — tokens signed by any other
        # ALB are rejected even if AWS's regional key endpoint would verify them.
        { name = "GHOSTMODE_ALB_ARN", value = data.aws_lb.phenom.arn },
        # osint #30: INT members with private GitHub emails are matched by
        # login via this map (the profile API returns null for them).
        { name = "GHOSTMODE_GITHUB_LOGIN_MAP", value = jsonencode({ "matt@sanmarcsoft.com" = "smsmatt" }) },
        # osint #58: remote sensors (the thephenom.app Lightsail honeypot)
        # POST events to /api/canary-ingest, which appends here. Setting the
        # path turns the dashboard opencanary tile into a liveness signal for
        # the real AWS sensor (status running/stale via last-write age),
        # instead of a permanent `not_configured` on this sensorless instance.
        { name = "OPENCANARY_LOG", value = "/var/log/opencanary/opencanary.log" }
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
        },
        {
          name      = "NTFY_PASS"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:ntfy_pass::"
        },
        {
          name      = "MAXMIND_ACCOUNT_ID"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:maxmind_account_id::"
        },
        {
          name      = "MAXMIND_LICENSE_KEY"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:maxmind_license_key::"
        },
        {
          name      = "GHOSTMODE_MCP_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:ghostmode_mcp_token::"
        },
        {
          name      = "GHOSTMODE_METRICS_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:ghostmode_metrics_token::"
        },
        {
          # osint #25: scoped read-only token (Analytics + Firewall Services
          # Read). CF_AUTH_EMAIL/CF_AUTH_KEY above are transitional and go
          # away once the Global key is rotated.
          name      = "CF_API_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:cf_api_token::"
        },
        {
          # osint #30: fine-grained PAT (Phenom-earth, Members: Read-only) —
          # was live in the hand-edited task-def but missing here; without
          # this mapping a terraform apply silently drops the ops gate.
          name      = "GITHUB_ORG_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:github_org_token::"
        },
        {
          # Same drift: present in the live task-def, was absent from source.
          name      = "LINEAR_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:linear_api_key::"
        },
        {
          # osint #58: Bearer that gates POST /api/canary-ingest (the
          # nest_canary_ingest ALB rule forwards that path without Cognito).
          # Same token the Lightsail pusher presents on its second push leg.
          name      = "GHOSTMODE_INGEST_TOKEN"
          valueFrom = "${aws_secretsmanager_secret.nest_secrets.arn}:ghostmode_ingest_token::"
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
    security_groups  = [aws_security_group.nest.id, data.aws_security_group.ecs_tasks.id]
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
