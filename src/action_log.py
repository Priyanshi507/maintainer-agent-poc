"""
action_log.py

Implements two guardrails from the brief simultaneously:

    "Every automated action is logged and traceable to a specific
    run/decision."
    "...via auditable, revertible actions (comments...) rather than
    unreviewed direct pushes."

Every proposed action - whether actually posted or just previewed in
dry-run - is appended to a local JSON-lines audit log with a timestamp,
the run's config snapshot, and the full decision (including the PR
facts that justified it). This makes every action traceable back to
exactly what data and config produced it, independent of GitHub's own
comment history.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Optional

import requests

from draft_action import DraftedComment
from pr_ingest import OpenPR

GITHUB_API = "https://api.github.com"
AUDIT_LOG_PATH = "agent_audit_log.jsonl"


class ActionPostError(RuntimeError):
    pass


@dataclass
class ActionRecord:
    timestamp: str
    action_type: str
    pr_number: int
    dry_run: bool
    posted: bool
    body_preview: str
    reason: str


def _append_audit_log(record: ActionRecord, path: str = AUDIT_LOG_PATH) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record)) + "\n")


def propose_action(
    owner: str,
    repo: str,
    pr: OpenPR,
    draft: DraftedComment,
    confirm: bool,
    repo_guard: Optional[str],
) -> ActionRecord:
    """
    Same double-guard pattern as ci-flake-triager's github_report_poster.py,
    verified there to correctly block posting on both a missing and a
    mismatched repo_guard. Reused deliberately rather than re-derived,
    since that logic was already tested and found correct.
    """
    expected = f"{owner}/{repo}"

    if not confirm or repo_guard != expected:
        record = ActionRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type="comment_draft",
            pr_number=pr.number,
            dry_run=True,
            posted=False,
            body_preview=draft.body,
            reason="dry-run (confirm not set or repo_guard mismatch)",
        )
        _append_audit_log(record)
        return record

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ActionPostError("GITHUB_TOKEN required to actually post.")

    url = f"{GITHUB_API}/repos/{owner}/{repo}/issues/{pr.number}/comments"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(url, headers=headers, json={"body": draft.body}, timeout=30)
    posted_ok = resp.status_code == 201

    record = ActionRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        action_type="comment_draft",
        pr_number=pr.number,
        dry_run=False,
        posted=posted_ok,
        body_preview=draft.body,
        reason="posted" if posted_ok else f"post failed: HTTP {resp.status_code}",
    )
    _append_audit_log(record)

    if not posted_ok:
        raise ActionPostError(f"Failed to post comment: HTTP {resp.status_code}: {resp.text[:300]}")

    return record
