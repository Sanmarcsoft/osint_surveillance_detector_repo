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

# Bearer tokens for the app's non-OIDC surfaces (osint #22/#28): /mcp (AI
# agents) and /metrics (Prometheus scrape). These were random_password
# resources, but they are NOT in state (and importing a random_password is
# lossy — it can't recover length/special, so the next plan force-rotates the
# live token). Like the other externally-rotated secrets here, the live values
# live in the secret and are held by ignore_changes below; the keys are
# documented in the jsonencode so a from-scratch rebuild still provisions them
# (generate 48-char no-special, then put-secret-value).
resource "aws_secretsmanager_secret" "nest_secrets" {
  name = "${local.project_name}/${local.service_name}/secrets"

  tags = local.tags
}

resource "aws_secretsmanager_secret_version" "nest_secrets" {
  secret_id = aws_secretsmanager_secret.nest_secrets.id

  secret_string = jsonencode({
    cf_auth_email           = var.cf_auth_email
    cf_auth_key             = var.cf_auth_key
    grafana_admin_password  = random_password.grafana_admin.result
    postgres_password       = random_password.postgres.result
    umami_database_url      = "postgresql://umami:${random_password.postgres.result}@127.0.0.1:5432/umami"
    linear_api_key          = var.linear_api_key
    github_org_token        = var.github_org_token
    # ghostmode_mcp_token / ghostmode_metrics_token: externally rotated,
    # values held by ignore_changes (48-char no-special bearer tokens).
    ghostmode_mcp_token     = var.ghostmode_mcp_token
    ghostmode_metrics_token = var.ghostmode_metrics_token
    cf_api_token            = var.cf_api_token
    # osint #58: shared canary-ingest Bearer (also held by the Lightsail
    # pusher + crabkey). Externally rotated, added via put-secret-value
    # 2026-06-11 — ignore_changes below protects the live value.
    ghostmode_ingest_token = var.ghostmode_ingest_token
  })

  # Tokens are rotated out-of-band (cf_api_token osint #25, github_org_token
  # osint #30 — both rotated 2026-06-04 via put-secret-value). Without this,
  # an apply with stale tfvars silently reverts the rotation and re-breaks
  # the ops gate. To change the secret SHAPE (add/remove keys), update via
  # put-secret-value first, then mirror the keys here for documentation.
  lifecycle {
    ignore_changes = [secret_string]
  }
}
