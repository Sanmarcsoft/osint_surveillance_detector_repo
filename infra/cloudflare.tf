# -----------------------------------------------------------------------------
# Cloudflare — DNS CNAME for nest-ops.thephenom.app (NOT dev-nest: that is the
# Cloudflare Pages SPA; pointing it at the ALB would break the live app)
# -----------------------------------------------------------------------------

resource "cloudflare_record" "nest_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "nest-ops"
  content = data.aws_lb.phenom.dns_name
  type    = "CNAME"
  proxied = true
}
