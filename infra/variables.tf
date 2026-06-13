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
  default     = "rg.fr-par.scw.cloud/sanmarcsoft/nest-ops:nix"
}

variable "cognito_domain" {
  description = "Cognito user pool domain prefix"
  type        = string
  default     = "phenom-dev-nest-auth"
}

# Cognito auth for this service is the SHARED phenom-prod pool (the same one
# Hasura/GraphQL uses), wired by hand and confirmed live on the ALB rule. This
# module therefore REFERENCES that pool/client/domain by ID rather than
# creating its own — the previous code created a phantom dev-local pool client
# that nothing used, and a name-match data source ("phem dev - 1jvngd") that
# returned empty and poisoned every plan. Defaults below are the live values.
variable "cognito_user_pool_id" {
  description = "Cognito user pool ID for ALB auth (shared phenom-prod pool)."
  type        = string
  default     = "us-east-1_knEL7cqS3"
}

variable "cognito_user_pool_client_id" {
  description = "Cognito app-client ID the ALB authenticates with (shared phenom-prod client)."
  type        = string
  default     = "1s0ccjm1ttsno43peb66834c05"
}

variable "cognito_user_pool_domain" {
  description = "Cognito hosted-UI domain prefix for ALB auth (shared phenom-prod domain)."
  type        = string
  default     = "phenom-prod-hasura-auth"
}

variable "create_cognito_domain" {
  description = "Whether to create the Cognito user pool domain. Default false: this service uses the shared phenom-prod hosted-UI domain, it does not own one."
  type        = bool
  default     = false
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

variable "ghostmode_ingest_token" {
  description = "Shared Bearer for POST /api/canary-ingest — remote OpenCanary sensors (the thephenom.app Lightsail honeypot) present it; crabkey holds the same value. Rotated out-of-band; ignore_changes protects the live secret (osint #58)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "cf_api_token" {
  description = "Scoped Cloudflare API token (Analytics + Firewall Services Read, zone-scoped). Replaces the Global key (osint #25)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "ghostmode_mcp_token" {
  description = "Bearer for /mcp (AI agents). 48-char no-special. Externally rotated; ignore_changes holds the live value (osint #22/#28)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "ghostmode_metrics_token" {
  description = "Bearer for /metrics (Prometheus scrape). 48-char no-special. Externally rotated; ignore_changes holds the live value (osint #22/#28)."
  type        = string
  sensitive   = true
  default     = ""
}
