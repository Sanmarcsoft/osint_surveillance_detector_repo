# -----------------------------------------------------------------------------
# Cognito — ALB authentication for N.E.S.T. Ops
# -----------------------------------------------------------------------------

locals {
  cognito_user_pool_id = tolist(data.aws_cognito_user_pools.phenom.ids)[0]
}

resource "aws_cognito_user_pool_domain" "nest" {
  count = var.create_cognito_domain ? 1 : 0

  domain       = var.cognito_domain
  user_pool_id = local.cognito_user_pool_id
}

resource "aws_cognito_user_pool_client" "nest" {
  name         = "phenom-dev-nest-ops"
  user_pool_id = local.cognito_user_pool_id

  generate_secret = true

  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  callback_urls = ["https://${local.fqdn}/oauth2/idpresponse"]
  logout_urls   = ["https://${local.fqdn}/"]

  supported_identity_providers = ["COGNITO"]
}

resource "aws_cognito_user_group" "nest_ops" {
  name         = "dev-nest-ops"
  user_pool_id = local.cognito_user_pool_id
}
