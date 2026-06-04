"""Tests for ghostmode.alb_auth — ALB OIDC JWT signature verification (osint #22).

The x-amzn-oidc-data header is an ES256 JWT signed by the ALB. The app MUST
verify the signature against the ALB regional public-key endpoint and fail
closed on any error. Decoding the payload without verification is the exact
vulnerability these tests exist to prevent.
"""

import base64
import json
import time

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from ghostmode import alb_auth


# --- helpers -----------------------------------------------------------------

def _make_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private_key, public_pem


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign_alb_jwt(private_key, claims: dict, header_extra: dict | None = None,
                  alb_padded: bool = False) -> str:
    """Craft an ALB-style ES256 JWT. ALB pads its base64 segments with '='
    (violating RFC 7515); alb_padded=True reproduces that quirk."""
    import jwt as pyjwt
    header = {
        "typ": "JWT",
        "alg": "ES256",
        "kid": "test-kid-1234",
        "signer": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/abc",
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TESTPOOL",
    }
    if header_extra:
        header.update(header_extra)
    token = pyjwt.encode(claims, private_key, algorithm="ES256", headers=header)
    if alb_padded:
        parts = token.split(".")
        padded = [p + "=" * (-len(p) % 4) for p in parts]
        token = ".".join(padded)
    return token


def _sign_alb_jwt_padded_signing_input(private_key, claims: dict) -> str:
    """Craft a JWT the way the real ALB does (osint #29): the header and
    payload segments are '='-padded base64 AND the ES256 signature is computed
    over that padded signing input. Stripping the padding before verification
    changes the signed message and must NOT be the only path tried."""
    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
    )
    from cryptography.hazmat.primitives import hashes

    def _b64pad(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode()  # keeps '=' padding

    header = {
        "typ": "JWT",
        "alg": "ES256",
        "kid": "test-kid-1234",
        "signer": "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/abc",
    }
    signing_input = (
        _b64pad(json.dumps(header).encode())
        + "."
        + _b64pad(json.dumps(claims).encode())
    )
    der_sig = private_key.sign(signing_input.encode(), _ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der_sig)
    raw_sig = r.to_bytes(32, "big") + s.to_bytes(32, "big")
    return signing_input + "." + _b64pad(raw_sig)


@pytest.fixture()
def keypair(monkeypatch):
    private_key, public_pem = _make_keypair()
    # Never hit the network in tests: stub the regional key fetch.
    monkeypatch.setattr(alb_auth, "_fetch_public_key", lambda kid, region: public_pem)
    alb_auth._key_cache.clear()
    return private_key, public_pem


def _valid_claims():
    return {"email": "agent@sanmarcsoft.com", "sub": "abc-123",
            "exp": int(time.time()) + 120}


# --- signature verification --------------------------------------------------

def test_valid_token_returns_claims(keypair):
    private_key, _ = keypair
    token = _sign_alb_jwt(private_key, _valid_claims())
    claims = alb_auth.verify_alb_jwt(token)
    assert claims is not None
    assert claims["email"] == "agent@sanmarcsoft.com"


def test_alb_padded_segments_accepted(keypair):
    """ALB emits '='-padded base64 segments; verification must handle them."""
    private_key, _ = keypair
    token = _sign_alb_jwt(private_key, _valid_claims(), alb_padded=True)
    claims = alb_auth.verify_alb_jwt(token)
    assert claims is not None
    assert claims["email"] == "agent@sanmarcsoft.com"


def test_alb_padded_signing_input_accepted(keypair):
    """osint #29 — the real ALB signs the PADDED segments. A token whose
    signature covers the padded signing input must verify; stripping padding
    first breaks ES256 and locked every user out of the ECS boards."""
    private_key, _ = keypair
    token = _sign_alb_jwt_padded_signing_input(private_key, _valid_claims())
    claims = alb_auth.verify_alb_jwt(token)
    assert claims is not None
    assert claims["email"] == "agent@sanmarcsoft.com"


def test_padded_signing_input_tampered_payload_rejected(keypair):
    """The raw-token verification path must still fail closed on tampering."""
    private_key, _ = keypair
    token = _sign_alb_jwt_padded_signing_input(private_key, _valid_claims())
    head, payload, sig = token.split(".")
    evil = json.loads(base64.urlsafe_b64decode(payload))
    evil["email"] = "attacker@evil.example"
    evil_payload = base64.urlsafe_b64encode(json.dumps(evil).encode()).decode()
    assert alb_auth.verify_alb_jwt(".".join([head, evil_payload, sig])) is None


def test_tampered_payload_rejected(keypair):
    private_key, _ = keypair
    token = _sign_alb_jwt(private_key, _valid_claims())
    head, payload, sig = token.split(".")
    evil = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    evil["email"] = "attacker@evil.example"
    token = ".".join([head, _b64url(json.dumps(evil).encode()), sig])
    assert alb_auth.verify_alb_jwt(token) is None


def test_wrong_key_rejected(keypair):
    other_key, _ = _make_keypair()
    token = _sign_alb_jwt(other_key, _valid_claims())
    assert alb_auth.verify_alb_jwt(token) is None


def test_expired_token_rejected(keypair):
    private_key, _ = keypair
    claims = _valid_claims()
    claims["exp"] = int(time.time()) - 60
    token = _sign_alb_jwt(private_key, claims)
    assert alb_auth.verify_alb_jwt(token) is None


def test_alg_none_rejected(keypair):
    """alg=none forgery must never pass."""
    header = _b64url(json.dumps({"typ": "JWT", "alg": "none",
                                 "kid": "test-kid-1234"}).encode())
    payload = _b64url(json.dumps(_valid_claims()).encode())
    assert alb_auth.verify_alb_jwt(f"{header}.{payload}.") is None


def test_garbage_rejected(keypair):
    assert alb_auth.verify_alb_jwt("not-a-jwt") is None
    assert alb_auth.verify_alb_jwt("") is None
    assert alb_auth.verify_alb_jwt(None) is None


def test_missing_kid_rejected(keypair):
    private_key, _ = keypair
    import jwt as pyjwt
    token = pyjwt.encode(_valid_claims(), private_key, algorithm="ES256",
                         headers={"typ": "JWT"})  # no kid
    assert alb_auth.verify_alb_jwt(token) is None


def test_unexpected_signer_rejected(keypair, monkeypatch):
    """When GHOSTMODE_ALB_ARN is configured, the JWT header's signer must match."""
    private_key, _ = keypair
    monkeypatch.setenv(
        "GHOSTMODE_ALB_ARN",
        "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/REAL/def",
    )
    token = _sign_alb_jwt(private_key, _valid_claims())  # signer .../test/abc
    assert alb_auth.verify_alb_jwt(token) is None


def test_matching_signer_accepted(keypair, monkeypatch):
    private_key, _ = keypair
    monkeypatch.setenv(
        "GHOSTMODE_ALB_ARN",
        "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/app/test/abc",
    )
    token = _sign_alb_jwt(private_key, _valid_claims())
    assert alb_auth.verify_alb_jwt(token) is not None


def test_kid_path_traversal_rejected(keypair):
    """kid is interpolated into a key-fetch URL; reject non [a-zA-Z0-9-] kids."""
    private_key, _ = keypair
    token = _sign_alb_jwt(private_key, _valid_claims(),
                          header_extra={"kid": "../../evil"})
    assert alb_auth.verify_alb_jwt(token) is None


def test_key_fetch_failure_fails_closed(keypair, monkeypatch):
    private_key, _ = keypair

    def boom(kid, region):
        raise RuntimeError("network down")

    monkeypatch.setattr(alb_auth, "_fetch_public_key", boom)
    alb_auth._key_cache.clear()
    token = _sign_alb_jwt(private_key, _valid_claims())
    assert alb_auth.verify_alb_jwt(token) is None
