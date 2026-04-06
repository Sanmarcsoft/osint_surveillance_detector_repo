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
