# -----------------------------------------------------------------------------
# ACM Certificate — dev-nest.thephenom.app with DNS validation via Cloudflare
# -----------------------------------------------------------------------------

resource "aws_acm_certificate" "nest" {
  domain_name       = local.fqdn
  validation_method = "DNS"

  tags = local.tags

  lifecycle {
    create_before_destroy = true
  }
}

resource "cloudflare_record" "acm_validation" {
  for_each = {
    for dvo in aws_acm_certificate.nest.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  zone_id = var.cloudflare_zone_id
  name    = each.value.name
  content = each.value.record
  type    = each.value.type
  ttl     = 60
  proxied = false
}

resource "aws_acm_certificate_validation" "nest" {
  certificate_arn         = aws_acm_certificate.nest.arn
  validation_record_fqdns = [for record in cloudflare_record.acm_validation : record.hostname]
}
