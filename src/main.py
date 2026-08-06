"""
main.py

Orchestrates the full pipeline in an order that matters for safety:
kill-switch check FIRST (before any GitHub API call), then ingest, then
per-PR drafting + verification, then propose (dry-run by default).

Usage:
    export GITHUB_TOKEN=ghp_xxx
    export GEMINI_API_KEY=AIzaxxxxxxxx
    python3 main.py --owner OWNER --repo REPO

    # Actually post (requires config enabled: true AND explicit flags):
    python3 main.py --owner OWNER --repo REPO --confirm --repo-guard OWNER/REPO
"""

from __future__ import annotations

import argparse
import sys

from config import load_config, enforce_kill_switch, AgentDisabledError
from pr_ingest import fetch_open_prs, filter_stale, PRIngestError
from draft_action import draft_nudge_comment, DraftError
from action_log import propose_action, ActionPostError


def run(owner: str, repo: str, confirm: bool, repo_guard: str | None) -> None:
    config = load_config()
    try:
        enforce_kill_switch(config)
    except AgentDisabledError as e:
        print(f"REFUSING TO RUN: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Kill-switch check passed (enabled=True). Fetching open PRs for {owner}/{repo}...", file=sys.stderr)

    try:
        prs = fetch_open_prs(owner, repo)
    except PRIngestError as e:
        print(f"Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)

    stale = filter_stale(prs, config.stale_pr_days_threshold)
    print(f"Found {len(prs)} open PRs, {len(stale)} stale (>= {config.stale_pr_days_threshold} days).", file=sys.stderr)

    actions_taken = 0
    for pr in stale:
        if actions_taken >= config.max_actions_per_run:
            print(f"Reached max_actions_per_run ({config.max_actions_per_run}), stopping.", file=sys.stderr)
            break
        try:
            draft = draft_nudge_comment(pr)
        except DraftError as e:
            print(f"  PR #{pr.number}: draft failed/rejected: {e}", file=sys.stderr)
            continue

        try:
            record = propose_action(owner, repo, pr, draft, confirm, repo_guard)
        except ActionPostError as e:
            print(f"  PR #{pr.number}: post failed: {e}", file=sys.stderr)
            continue

        status = "POSTED" if record.posted else "dry-run only"
        print(f"  PR #{pr.number} ({status}): {record.body_preview[:100]}", file=sys.stderr)
        actions_taken += 1

    print(f"\nDone. {actions_taken} action(s) processed. See agent_audit_log.jsonl for full trace.", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prototype AI maintainer assistant - stale PR nudge agent")
    parser.add_argument("--owner", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--confirm", action="store_true", help="Actually post comments (requires --repo-guard too)")
    parser.add_argument("--repo-guard", default=None, help="Must exactly equal 'owner/repo' to actually post")
    args = parser.parse_args()

    run(args.owner, args.repo, args.confirm, args.repo_guard)
