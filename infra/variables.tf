variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "cloudflare_api_token" {
  description = "Cloudflare API token"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare zone ID for thephenom.app"
  type        = string
  default     = "637c0036b564b56f7257815b23bd2e17"
}

variable "cf_auth_email" {
  description = "Cloudflare auth email for Ghost Mode runtime"
  type        = string
  sensitive   = true
}

variable "cf_auth_key" {
  description = "Cloudflare auth key for Ghost Mode runtime"
  type        = string
  sensitive   = true
}

variable "ghostmode_image" {
  description = "Docker image for the Ghost Mode container"
  type        = string
  # Live deploy uses the ECR image (built on ai), NOT the Scaleway Nix image.
  default     = "657033058608.dkr.ecr.us-east-1.amazonaws.com/phenom-dev/nest-ops:latest"
}

variable "cognito_domain" {
  description = "Cognito user pool domain prefix"
  type        = string
  default     = "phenom-dev-nest-auth"
}

variable "create_cognito_domain" {
  description = "Whether to create the Cognito user pool domain"
  type        = bool
  default     = true
}

variable "listener_rule_priority" {
  description = "Priority for the ALB listener rule"
  type        = number
  default     = 104
}

variable "linear_api_key" {
  description = "Linear API key for Ghost Mode integrations"
  type        = string
  sensitive   = true
  default     = ""
}

variable "github_org_token" {
  description = "GitHub organization token for Ghost Mode integrations"
  type        = string
  sensitive   = true
  default     = ""
}

# Secrets stored in nest_secrets and consumed by the running task. NO defaults:
# a missing value fails the plan rather than silently wiping the live secret.
# Supply via tfvars sourced from pass (sanmarcsoft/ntfy/*, sanmarcsoft/maxmind/*).
variable "ntfy_pass" {
  description = "ntfy publisher password (ghostmode-publisher) — /health + alerts"
  type        = string
  sensitive   = true
}

variable "maxmind_account_id" {
  description = "MaxMind account ID — threat-map geoip"
  type        = string
  sensitive   = true
}

variable "maxmind_license_key" {
  description = "MaxMind license key — threat-map geoip"
  type        = string
  sensitive   = true
}

variable "synapse_db_password" {
  description = "Synapse DB password held in nest_secrets (preserved across applies)"
  type        = string
  sensitive   = true
}
