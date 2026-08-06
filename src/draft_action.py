"""
draft_action.py

Generates a draft "nudge" comment for a stale PR - the safest possible
action from the brief's Phase 1 scope ("comments, labels, draft PRs"
explicitly listed as the auditable/revertible action set, as opposed to
direct merges).

The verification discipline here is the same one built and tested in
ci-flake-triager's anti-hallucination check, applied to a different
claim: instead of verifying a quoted log line appears verbatim in the
source log, this verifies that any PR number, day-count, or author name
the draft comment states matches the real ingested data exactly. An
agent that's allowed to draft comments about PRs is an agent that could
misstate which PR, how stale, or who authored it - and getting that
wrong in a comment posted to a real maintainer's repo is a credibility
problem for the whole system, not a cosmetic one.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from pr_ingest import OpenPR


class DraftError(RuntimeError):
    pass


@dataclass
class DraftedComment:
    pr_number: int
    body: str


DRAFT_PROMPT_TEMPLATE = """You are drafting a polite, brief nudge comment for a stale open-source pull request. The PR has not been updated in a while and may need attention from its author or a reviewer.

Facts about this PR (use ONLY these facts, do not invent additional details):
- PR number: {number}
- Title: {title}
- Author: {author}
- Days since last update: {days}

Write a short (2-3 sentence), friendly, non-accusatory comment that:
1. Explicitly writes "PR #{number}" or "#{number}" somewhere in the text (not just the title) - this is required, not optional.
2. States the exact day count ({days}) from the facts above somewhere in the text.
3. Asks if it's still being worked on or needs help.
4. Does not assume anything about WHY it's stale (could be waiting on review, could be paused - don't guess).

Output only the comment text, nothing else."""



def build_prompt(pr: OpenPR) -> str:
    return DRAFT_PROMPT_TEMPLATE.format(
        number=pr.number, title=pr.title, author=pr.author, days=pr.days_since_update
    )


def _verify_draft_facts(body: str, pr: OpenPR) -> None:
    """
    Mechanical check: the drafted comment must reference the correct PR
    number and day count. This doesn't guarantee the prose is good, but
    it guarantees the agent didn't hallucinate a different PR's details
    into this comment - the specific failure mode that would be most
    damaging if it reached a real maintainer's repo.
    """
    if str(pr.number) not in body:
        raise DraftError(
            f"Drafted comment for PR #{pr.number} does not mention the PR number "
            f"anywhere in the text - refusing to treat this as verified. Body: {body[:200]!r}"
        )
    if str(pr.days_since_update) not in body:
        raise DraftError(
            f"Drafted comment for PR #{pr.number} does not state the correct day "
            f"count ({pr.days_since_update}) anywhere in the text - possible "
            f"hallucinated or stale figure. Body: {body[:200]!r}"
        )


def draft_nudge_comment(pr: OpenPR, api_key: Optional[str] = None) -> DraftedComment:
    try:
        from google import genai
    except ImportError as e:
        raise DraftError("The 'google-genai' package is required: pip install google-genai") from e

    key = api_key or os.environ.get("GEMINI_API_KEY")
    if not key:
        raise DraftError("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=key)
    prompt = build_prompt(pr)
    model_name = os.environ.get("GEMINI_MODEL", "models/gemini-flash-latest")

    response = client.models.generate_content(model=model_name, contents=prompt)
    body = response.text.strip()

    _verify_draft_facts(body, pr)

    return DraftedComment(pr_number=pr.number, body=body)
