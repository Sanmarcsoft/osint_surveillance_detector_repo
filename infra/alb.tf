# -----------------------------------------------------------------------------
# ALB — Listener certificate, target group, and listener rule with Cognito auth
# -----------------------------------------------------------------------------

resource "aws_lb_listener_certificate" "nest" {
  listener_arn    = data.aws_lb_listener.https.arn
  certificate_arn = aws_acm_certificate_validation.nest.certificate_arn
}

resource "aws_lb_target_group" "nest" {
  name        = "${local.project_name}-${local.service_name}"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.phenom.id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/health"
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  tags = local.tags
}

# Canary-ingest bypass (osint #54): remote OpenCanary sensors POST events
# with a bearer token; ghostmode's GhostmodeAuthMiddleware gates the route
# (GHOSTMODE_INGEST_TOKEN), so the ALB must forward WITHOUT Cognito — the
# sensors are machines, not humans with browser sessions.
resource "aws_lb_listener_rule" "nest_canary_ingest" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.listener_rule_priority - 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nest.arn
  }

  condition {
    host_header {
      values = [local.fqdn]
    }
  }

  condition {
    path_pattern {
      values = ["/api/canary-ingest"]
    }
  }

  tags = local.tags
}

# Metrics-scrape bypass: ops.sanmarcsoft.com Prometheus scrapes ghostmode's
# /metrics with a bearer token (GHOSTMODE_METRICS_TOKEN); ghostmode's auth
# middleware gates the route, so the ALB must forward WITHOUT Cognito — the
# scraper is a machine, not a browser session (same pattern as canary-ingest).
resource "aws_lb_listener_rule" "nest_metrics" {
  listener_arn = data.aws_lb_listener.https.arn
  # priority 101 (base 104 → -3): -2 (=102) collided with a non-osint rule
  # already on the shared ev-alb listener; 101 is the free slot below canary (103).
  priority     = var.listener_rule_priority - 3

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nest.arn
  }

  condition {
    host_header {
      values = [local.fqdn]
    }
  }

  condition {
    path_pattern {
      values = ["/metrics"]
    }
  }

  tags = local.tags
}

# MCP bypass (osint #85): internal agents call /mcp with a bearer token
# (GHOSTMODE_MCP_TOKEN) and GhostmodeAuthMiddleware gates the route, so the ALB
# must forward WITHOUT Cognito - same pattern as canary-ingest and metrics.
# This carve-out was missing. The "nest" rule below is a host-wide catch-all
# that declares authenticate-cognito, and its live counterpart has drifted to a
# bare forward; the moment an apply reconciles that drift, /mcp would sit behind
# a browser login and every agent bearer call would be redirected instead of
# served. Priority 99 (base 104 - 5): 100 to 103 are taken on this shared
# listener.
resource "aws_lb_listener_rule" "nest_mcp" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.listener_rule_priority - 5

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nest.arn
  }

  condition {
    host_header {
      values = [local.fqdn]
    }
  }

  condition {
    path_pattern {
      values = ["/mcp", "/mcp/*"]
    }
  }

  tags = local.tags
}

# Health bypass (osint #85): /health is the service's public liveness endpoint and
# GhostmodeAuthMiddleware serves it anonymously by design. The "nest" rule below is
# a host-wide catch-all declaring authenticate-cognito, so restoring that rule put
# /health behind a browser login: an unauthenticated GET returned 302 to
# auth.thephenom.app instead of 200. The ALB target-group check did not notice,
# because it probes the task IP directly and never traverses a listener rule, so
# the regression is invisible from AWS health and only shows up to external
# probes. Priority 98 (base 104 - 6): 99 to 103 are taken.
resource "aws_lb_listener_rule" "nest_health" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.listener_rule_priority - 6

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nest.arn
  }

  condition {
    host_header {
      values = [local.fqdn]
    }
  }

  condition {
    path_pattern {
      values = ["/health"]
    }
  }

  tags = local.tags
}

resource "aws_lb_listener_rule" "nest" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.listener_rule_priority

  action {
    type = "authenticate-cognito"

    authenticate_cognito {
      user_pool_arn              = "arn:aws:cognito-idp:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:userpool/${local.cognito_user_pool_id}"
      user_pool_client_id        = var.cognito_user_pool_client_id
      user_pool_domain           = var.cognito_user_pool_domain
      on_unauthenticated_request = "authenticate"
      session_timeout            = 28800
      scope                      = "openid email profile"
    }
  }

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.nest.arn
  }

  condition {
    host_header {
      values = [local.fqdn]
    }
  }

  tags = local.tags
}
