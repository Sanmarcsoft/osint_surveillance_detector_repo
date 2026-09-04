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
  description = "Docker image for the Ghost Mode container (build-push.yml pushes here)"
  type        = string
  # Back on Scaleway (osint #87, 2026-09-04), which is where production images
  # belong. The three-month ECR detour is over: the Nix image did not "crash on
  # startup" for any mysterious reason, it was missing 9 of the 13 Python
  # modules the app imports, so `ghostmode serve` raised ImportError on fastmcp
  # before logging existed and the container exited 1 silently. Fixed in #88
  # (flake.nix closure + flake.lock + tests/test_nix_runtime_deps.py).
  #
  # Pinned to the commit tag, never :testing or :latest. A rolling tag means the
  # running container and this file can disagree without anything changing here,
  # which is the same class of drift that let task defs :56 to :63 be registered
  # out of band while state still held :55. Nothing in this repo registers task
  # definitions, so the tag here IS the deploy record.
  #
  # Built by build-push.yml run 33871610423 from 3fdd667. Verified before it was
  # pointed at production: on mini (native x86_64-linux) the same derivation
  # imports all 13 modules plus ghostmode.mcp_server under Python 3.14.7, and
  # `ghostmode serve` answers /health with {"ok":true,"mode":"nest"} in 2s.
  # aws_ecs_service.nest now has a deployment circuit breaker with rollback, so
  # a bad image fails the deployment instead of stalling the apply.
  default = "rg.fr-par.scw.cloud/sanmarcsoft/ghostmode:git-3fdd6676e167"
}

variable "scaleway_registry_access_key" {
  description = "Scaleway Container Registry access key (ECS image pull)"
  type        = string
  sensitive   = true
}

variable "scaleway_registry_secret_key" {
  description = "Scaleway Container Registry secret key (ECS image pull)"
  type        = string
  sensitive   = true
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
  description = "Cognito hosted-UI domain for ALB auth (shared phenom-prod custom domain)."
  type        = string
  # Must be the custom domain, not the "phenom-prod-hasura-auth" prefix (#85).
  # The phenom-prod pool has custom domain auth.thephenom.app ACTIVE, and once a
  # pool has one, ModifyRule rejects the prefix form with "The user pool domain
  # 'phenom-prod-hasura-auth' is not associated with the provided user pool".
  # That is what broke the 2026-09-04 apply, and it is the likely reason the
  # Cognito action was stripped from the live rule by hand on 2026-07-05: the
  # custom domain was added after these defaults were confirmed on 2026-06-11,
  # which silently invalidated the prefix and left the rule unappliable.
  default = "auth.thephenom.app"
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
