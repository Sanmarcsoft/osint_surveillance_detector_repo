"""Tests for ghostmode.github_auth — INT-team permission gate (osint #30).

The team-members API returns logins reliably, but members' public profile
emails are usually null (private). Matching only on public email locks out
legitimate INT members — the gate must also match via the configured
email→login map (GHOSTMODE_GITHUB_LOGIN_MAP).
"""

import json

import pytest

from ghostmode import github_auth


TEAM_MEMBERS = [{"login": "smsmatt"}, {"login": "jonathanhart"}]
PROFILES = {
    # smsmatt keeps his email private — the API returns null
    "smsmatt": {"login": "smsmatt", "email": None},
    "jonathanhart": {"login": "jonathanhart", "email": "jonathan.hart@gmail.com"},
}


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise github_auth.requests.HTTPError(f"{self.status_code}")


@pytest.fixture(autouse=True)
def _fresh_caches(monkeypatch):
    github_auth._membership_cache.clear()
    github_auth._team_cache.clear()

    def fake_get(url, **kwargs):
        if url.endswith("/teams/INT/members"):
            page = kwargs.get("params", {}).get("page", 1)
            return _FakeResponse(TEAM_MEMBERS if page == 1 else [])
        for login, profile in PROFILES.items():
            if url.endswith(f"/users/{login}"):
                return _FakeResponse(profile)
        return _FakeResponse({}, status_code=404)

    monkeypatch.setattr(github_auth.requests, "get", fake_get)
    yield


def test_member_matched_by_public_email():
    assert github_auth.check_team_membership(
        "jonathan.hart@gmail.com", "tok") is True


def test_member_with_private_email_matched_via_login_map(monkeypatch):
    """osint #30 — M's public GitHub email is null; the email match can never
    see him. The email→login map must grant membership via his login."""
    monkeypatch.setenv(
        "GHOSTMODE_GITHUB_LOGIN_MAP",
        json.dumps({"matt@sanmarcsoft.com": "smsmatt"}),
    )
    assert github_auth.check_team_membership(
        "matt@sanmarcsoft.com", "tok") is True


def test_login_map_entry_not_in_team_rejected(monkeypatch):
    """A mapped login that is NOT on the team must stay locked out."""
    monkeypatch.setenv(
        "GHOSTMODE_GITHUB_LOGIN_MAP",
        json.dumps({"intruder@evil.example": "not-a-member"}),
    )
    assert github_auth.check_team_membership(
        "intruder@evil.example", "tok") is False


def test_unmapped_private_email_rejected():
    assert github_auth.check_team_membership(
        "stranger@nowhere.example", "tok") is False


def test_malformed_login_map_fails_closed(monkeypatch):
    monkeypatch.setenv("GHOSTMODE_GITHUB_LOGIN_MAP", "{not json")
    assert github_auth.check_team_membership(
        "matt@sanmarcsoft.com", "tok") is False


def test_no_token_fails_closed():
    assert github_auth.check_team_membership("matt@sanmarcsoft.com", "") is False
    perms = github_auth.get_user_permissions("matt@sanmarcsoft.com", None)
    assert perms == {"int_team_member": False, "linear_enabled": False,
                     "ops_enabled": False}


def test_permissions_follow_membership(monkeypatch):
    monkeypatch.setenv(
        "GHOSTMODE_GITHUB_LOGIN_MAP",
        json.dumps({"matt@sanmarcsoft.com": "smsmatt"}),
    )
    perms = github_auth.get_user_permissions("matt@sanmarcsoft.com", "tok")
    assert perms["ops_enabled"] is True
