locals {
  project_name = "phenom-dev"
  service_name = "nest-ops"
  fqdn         = "nest-ops.thephenom.app"

  tags = {
    Environment = "development"
    Project     = "phenom"
    Service     = "nest-ops"
    ManagedBy   = "terraform"
  }
}
