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

resource "aws_lb_listener_rule" "nest" {
  listener_arn = data.aws_lb_listener.https.arn
  priority     = var.listener_rule_priority

  action {
    type = "authenticate-cognito"

    authenticate_cognito {
      user_pool_arn              = "arn:aws:cognito-idp:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:userpool/${local.cognito_user_pool_id}"
      user_pool_client_id        = aws_cognito_user_pool_client.nest.id
      user_pool_domain           = var.cognito_domain
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
