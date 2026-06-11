# -----------------------------------------------------------------------------
# Cloudflare — DNS CNAME for dev-nest.thephenom.app
# -----------------------------------------------------------------------------

resource "cloudflare_record" "nest_cname" {
  zone_id = var.cloudflare_zone_id
  name    = "dev-nest"
  content = data.aws_lb.phenom.dns_name
  type    = "CNAME"
  proxied = true
}
