#!/bin/bash
# Dual-push every OpenCanary event from the thephenom.app Lightsail honeypot.
#   1. crabkey (SanMarcSoft, the multi-tenant correlation service) — via
#      Cloudflare, IPv4 forced (the 3.230.47.213 allow rule is IPv4-only;
#      dual-stack hosts egress IPv6 first and get CF-challenged).
#   2. nest-ops (Phenom ops board, osint #58) — straight to the ALB via
#      --connect-to (bypasses Cloudflare). The /api/canary-ingest path is
#      forwarded WITHOUT Cognito by the `nest_canary_ingest` ALB rule and is
#      bearer-gated in the app by GHOSTMODE_INGEST_TOKEN.
#
# TOKEN is sourced from /etc/canary-push.env (chmod 600), never hardcoded.
# That same value lives in `pass sanmarcsoft/ghostmode/ingest-token`, in the
# nest-ops Secrets Manager secret (key ghostmode_ingest_token), and in crabkey.
set -euo pipefail
# shellcheck source=/dev/null
source /etc/canary-push.env   # defines TOKEN=...

ALB="phenom-dev-alb-1007680551.us-east-1.elb.amazonaws.com"
LOG="/var/log/opencanary/opencanary.log"

tail -n0 -F "$LOG" | while IFS= read -r line; do
  [ -z "$line" ] && continue
  payload="$(jq -nc --arg m "$line" '{message:$m}')"
  curl -s -4 -m6 -X POST https://crabkey.sanmarcsoft.com/api/canary-ingest \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    --data "$payload" >/dev/null 2>&1
  curl -s -4 -m6 -X POST --connect-to "nest-ops.thephenom.app:443:$ALB:443" \
    https://nest-ops.thephenom.app/api/canary-ingest \
    -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    --data "$payload" >/dev/null 2>&1
done
