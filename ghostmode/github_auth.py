"""GitHub organization/team membership checker.

Verifies whether a user (by email) is a member of a specific
GitHub org team. Used to gate INT-team features in N.E.S.T. Ops.
Caches results for 10 minutes per user.
"""
from __future__ import annotations

import time
import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"

# Cache: email -> (timestamp, is_member)
_membership_cache: dict[str, tuple[float, bool]] = {}
_CACHE_TTL = 600  # 10 minutes

# Cache: org/team -> (timestamp, member_emails)
_team_cache: dict[str, tuple[float, set[str]]] = {}
_TEAM_CACHE_TTL = 300  # 5 minutes


def check_team_membership(
    email: str,
    github_token: str,
    org: str = "Phenom-earth",
    team_slug: str = "INT",
) -> bool:
    """Check if a user email belongs to a GitHub org team.

    Fetches team members and matches by email (from public profile).
    Returns True if the user is a member, False otherwise.
    """
    if not email or not github_token:
        return False

    # Check per-user cache
    cache_key = f"{email}:{org}/{team_slug}"
    now = time.time()
    if cache_key in _membership_cache:
        ts, is_member = _membership_cache[cache_key]
        if now - ts < _CACHE_TTL:
            return is_member

    # Fetch team members (cached separately)
    members = _get_team_member_emails(github_token, org, team_slug)
    is_member = email.lower() in members

    _membership_cache[cache_key] = (now, is_member)
    return is_member


def _get_team_member_emails(
    github_token: str,
    org: str,
    team_slug: str,
) -> set[str]:
    """Fetch all member emails for a GitHub org team."""
    team_key = f"{org}/{team_slug}"
    now = time.time()
    if team_key in _team_cache:
        ts, emails = _team_cache[team_key]
        if now - ts < _TEAM_CACHE_TTL:
            return emails

    emails: set[str] = set()
    page = 1
    while True:
        try:
            resp = requests.get(
                f"{_GITHUB_API}/orgs/{org}/teams/{team_slug}/members",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"per_page": 100, "page": page},
                timeout=10,
            )
            if resp.status_code == 404:
                logger.warning("GitHub team %s/%s not found", org, team_slug)
                break
            resp.raise_for_status()
            members = resp.json()
        except requests.RequestException as e:
            logger.error("GitHub API error fetching team members: %s", e)
            break

        if not members:
            break

        # For each member, fetch their email from profile
        for member in members:
            user_email = _get_user_email(github_token, member.get("login", ""))
            if user_email:
                emails.add(user_email.lower())

        if len(members) < 100:
            break
        page += 1

    _team_cache[team_key] = (now, emails)
    return emails


def _get_user_email(github_token: str, username: str) -> Optional[str]:
    """Fetch a GitHub user's primary email."""
    if not username:
        return None
    try:
        resp = requests.get(
            f"{_GITHUB_API}/users/{username}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
            },
            timeout=5,
        )
        resp.raise_for_status()
        return resp.json().get("email") or None
    except requests.RequestException:
        return None


def get_user_permissions(
    email: str,
    github_token: Optional[str],
    org: str = "Phenom-earth",
    team_slug: str = "INT",
) -> dict:
    """Get feature permissions for a user.

    Returns: {"int_team_member": bool, "linear_enabled": bool, "ops_enabled": bool}
    """
    if not github_token:
        return {"int_team_member": False, "linear_enabled": False, "ops_enabled": False}

    is_member = check_team_membership(email, github_token, org, team_slug)
    return {
        "int_team_member": is_member,
        # These are server-side gates — actual toggle state is in client localStorage
        "linear_enabled": is_member,
        "ops_enabled": is_member,
    }
