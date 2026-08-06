"""
pr_ingest.py

Fetches open pull requests for a repo and computes staleness, mapping
directly to one of the brief's Phase 1 scoped deliverables:

    "PR hygiene: detect PRs that are behind main... and nudge stale
    PRs/reviewers after a configurable idle period."

Auth pattern (GITHUB_TOKEN, Bearer header) reused from the verified
ci-flake-triager project rather than rewritten from scratch, since that
pattern was already tested against a real repo and found correct.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

GITHUB_API = "https://api.github.com"


class PRIngestError(RuntimeError):
    pass


@dataclass
class OpenPR:
    number: int
    title: str
    html_url: str
    updated_at: str
    days_since_update: int
    author: str


def _auth_headers() -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise PRIngestError("GITHUB_TOKEN environment variable is not set.")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _days_since(iso_timestamp: str) -> int:
    """
    Computes staleness from GitHub's ISO 8601 updated_at field.
    Deliberately a pure function, tested in isolation (see
    tests/test_pr_ingest.py), because this is the single number that
    decides whether a real action (drafting a comment) is proposed at
    all - a date-math bug here would misfire the whole agent.
    """
    updated = datetime.fromisoformat(iso_timestamp.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    return (now - updated).days


def fetch_open_prs(owner: str, repo: str, limit: int = 20) -> list[OpenPR]:
    url = f"{GITHUB_API}/repos/{owner}/{repo}/pulls"
    params = {"state": "open", "per_page": limit, "sort": "updated", "direction": "asc"}
    resp = requests.get(url, headers=_auth_headers(), params=params, timeout=30)
    if resp.status_code != 200:
        raise PRIngestError(f"GitHub API returned {resp.status_code}: {resp.text[:300]}")

    prs = []
    for item in resp.json():
        prs.append(OpenPR(
            number=item["number"],
            title=item["title"],
            html_url=item["html_url"],
            updated_at=item["updated_at"],
            days_since_update=_days_since(item["updated_at"]),
            author=item["user"]["login"],
        ))
    return prs


def filter_stale(prs: list[OpenPR], threshold_days: int) -> list[OpenPR]:
    return [pr for pr in prs if pr.days_since_update >= threshold_days]
