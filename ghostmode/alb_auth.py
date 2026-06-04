"""ALB OIDC identity verification (osint #22).

AWS ALB forwards the authenticated user's claims in the `x-amzn-oidc-data`
header as an ES256 JWT signed by the load balancer. Trusting its payload
without verifying the signature lets anyone who can reach the target group
forge an identity. This module verifies:

- ES256 signature against the ALB regional public-key endpoint
  (https://public-keys.auth.elb.{region}.amazonaws.com/{kid})
- `exp` (token freshness)
- `signer` header matches GHOSTMODE_ALB_ARN when configured
- `kid` is sane before being interpolated into the key-fetch URL

Every failure path returns None — fail closed, never fall through to an
unverified identity.
"""

import base64
import json
import logging
import os
import re
import time

import jwt as pyjwt
import requests

logger = logging.getLogger("ghostmode.alb_auth")

_KID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
_KEY_TTL_SECONDS = 3600

# kid -> (fetched_at, pem)
_key_cache: dict = {}


def _region() -> str:
    return os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "us-east-1"))


def _fetch_public_key(kid: str, region: str) -> str:
    """Fetch the ALB ES256 public key (PEM) for a key id. Raises on failure."""
    url = f"https://public-keys.auth.elb.{region}.amazonaws.com/{kid}"
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    return resp.text


def _get_public_key(kid: str) -> str:
    now = time.time()
    cached = _key_cache.get(kid)
    if cached and now - cached[0] < _KEY_TTL_SECONDS:
        return cached[1]
    pem = _fetch_public_key(kid, _region())
    _key_cache[kid] = (now, pem)
    return pem


def _strip_padding(token: str) -> str:
    """ALB pads its JWT base64 segments with '=' (violating RFC 7515).
    Strip padding from each segment so standard JWT libraries accept it."""
    return ".".join(part.rstrip("=") for part in token.split("."))


def verify_alb_jwt(token):
    """Verify an x-amzn-oidc-data JWT. Returns the claims dict on success,
    None on ANY failure (fail closed)."""
    if not token or not isinstance(token, str):
        return None
    token = _strip_padding(token.strip())
    if token.count(".") != 2:
        return None

    # Decode the (unverified) header to find kid/alg/signer — used only to
    # select the verification key, never to grant access.
    try:
        header_b64 = token.split(".")[0]
        header = json.loads(
            base64.urlsafe_b64decode(header_b64 + "=" * (-len(header_b64) % 4))
        )
    except Exception:
        return None

    if header.get("alg") != "ES256":
        logger.warning("alb_auth: rejected token with alg=%r", header.get("alg"))
        return None

    kid = header.get("kid", "")
    if not _KID_RE.match(kid or ""):
        logger.warning("alb_auth: rejected token with invalid kid")
        return None

    expected_signer = os.getenv("GHOSTMODE_ALB_ARN", "")
    if expected_signer and header.get("signer") != expected_signer:
        logger.warning("alb_auth: rejected token with unexpected signer=%r",
                       header.get("signer"))
        return None

    try:
        public_key = _get_public_key(kid)
    except Exception as exc:
        logger.error("alb_auth: public key fetch failed for kid=%s: %s", kid, exc)
        return None

    try:
        claims = pyjwt.decode(
            token,
            public_key,
            algorithms=["ES256"],
            options={"require": ["exp"], "verify_exp": True},
        )
    except Exception as exc:
        logger.warning("alb_auth: signature verification failed: %s", exc)
        return None

    return claims


def identity_from_request_headers(headers) -> dict | None:
    """Extract and VERIFY the ALB identity from request headers.
    Returns verified claims or None."""
    return verify_alb_jwt(headers.get("x-amzn-oidc-data", ""))
