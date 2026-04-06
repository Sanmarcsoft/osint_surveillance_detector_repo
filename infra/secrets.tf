# -----------------------------------------------------------------------------
# Secrets — Generated passwords and Secrets Manager for N.E.S.T. Ops
# -----------------------------------------------------------------------------

resource "random_password" "grafana_admin" {
  length  = 32
  special = true
}

resource "random_password" "postgres" {
  length  = 32
  special = true
}

resource "aws_secretsmanager_secret" "nest_secrets" {
  name = "${local.project_name}/${local.service_name}/secrets"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "nest_secrets" {
  secret_id = aws_secretsmanager_secret.nest_secrets.id

  secret_string = jsonencode({
    cf_auth_email          = var.cf_auth_email
    cf_auth_key            = var.cf_auth_key
    grafana_admin_password = random_password.grafana_admin.result
    postgres_password      = random_password.postgres.result
    umami_database_url     = "postgresql://umami:${random_password.postgres.result}@127.0.0.1:5432/umami"
    linear_api_key         = var.linear_api_key
    github_org_token       = var.github_org_token
  })
}
