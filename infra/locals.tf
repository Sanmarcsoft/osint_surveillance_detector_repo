locals {
  project_name = "phenom-dev"
  service_name = "nest-ops"
  # nest-ops is the live host (ALB host rule, ACM cert, Cognito callback all key
  # off this). Was stale "dev-nest"; reality is nest-ops.
  fqdn         = "nest-ops.thephenom.app"

  tags = {
    Environment = "development"
    Project     = "phenom"
    Service     = "nest-ops"
    ManagedBy   = "terraform"
  }
}
