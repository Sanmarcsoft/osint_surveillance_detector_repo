# -----------------------------------------------------------------------------
# Cloudflare — DNS CNAME for nest-ops.thephenom.app
# -----------------------------------------------------------------------------

resource "cloudflare_record" "nest_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "nest-ops"
  content = data.aws_lb.phenom.dns_name
  type    = "CNAME"
  proxied = true
}
