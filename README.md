# Maintainer Assistant — Safety-Pattern Prototype

A small, honest proof-of-concept built as personal-project evidence for
the LFX "CNCF - Kyverno: AI Assistant" mentorship application.

## Why this exists, and why it's not tested against kyverno/kyverno

The project's GitHub issue (#16665) explicitly states, in the maintainer's
own final comment: *"Do not create PRs till the mentorship begins... Feel
free to prototype and explore, but save the details for your application
and video."* Consistent with that instruction, this prototype was built
and tested entirely outside the kyverno repository — against a repo I
own (`ci-flake-triager`) — rather than by opening PRs or posting on the
live, maintainer-monitored repo.

This is intentionally narrow: it implements one Phase 1 capability from
the brief (PR hygiene / stale-PR nudging) with full safety guardrails,
rather than attempting the whole proposal's scope.

## What it actually does

1. **`src/config.py`** — implements the brief's kill-switch requirement
   ("Rate-limited and kill-switch controlled... humans can override or
   disable per-repo/per-workflow via a config file") literally: a
   `.agent-config.yaml` with `enabled: false` by default. If the config
   file is missing entirely, the agent also defaults to disabled rather
   than assuming it's safe to run — see `tests/test_safety.py`, which
   verifies both the missing-file case and the explicit-false case block
   execution.

2. **`src/pr_ingest.py`** — fetches real open PRs via the GitHub API and
   computes staleness, the data behind the brief's "PR hygiene... nudge
   stale PRs/reviewers after a configurable idle period" deliverable.

3. **`src/draft_action.py`** — drafts a nudge comment via LLM, then
   mechanically verifies the draft actually states the correct PR number
   and day count before accepting it. This is the same anti-hallucination
   discipline built and verified in the ci-flake-triager project, applied
   to a different claim: instead of checking a quoted log line is
   verbatim, this checks the agent didn't misstate which PR or how stale
   it is — the failure mode most likely to embarrass a maintainer if it
   reached a real repo.

4. **`src/action_log.py`** — implements two more brief requirements at
   once: "auditable, revertible actions (comments...)" via a dry-run
   default requiring both `--confirm` and an exact `--repo-guard
   owner/repo` match to actually post (the same double-guard pattern
   verified in ci-flake-triager's `github_report_poster.py`), and "every
   automated action is logged and traceable to a specific run/decision"
   via a local JSON-lines audit log written on every action, dry-run or
   real.

## Honest status

All safety logic is built and unit-tested (`tests/test_safety.py`, 7
tests, all passing) — the kill-switch defaults, the staleness math, and
the fact-verification check are genuinely verified, not just described.

The full pipeline has been run end-to-end against a real PR on my own
`ci-flake-triager` repository (with the kill-switch enabled, a real
GitHub PR, and a real Gemini API call), and one real thing was found and
fixed in the process:

**The first draft prompt produced a comment that referenced the PR by
title instead of explicitly stating its number**, e.g. *"I noticed there
hasn't been any activity on this pull request ('test: trivial change...')
for 0 days"* — accurate, readable prose, but it failed the mechanical
fact-check (`_verify_draft_facts`), which requires the PR number to
appear explicitly, not just be implied by title context. The check
correctly rejected it rather than posting or logging it as verified. I
tightened the prompt to explicitly require writing `PR #{number}` or
`#{number}`, re-ran, and got a correct result:

```json
{"timestamp": "2026-08-06T19:31:38...", "action_type": "comment_draft",
 "pr_number": 1, "dry_run": true, "posted": false,
 "body_preview": "Hi @Priyanshi507, just checking in on PR #1 since it
 has been 0 days since the last update. Is this still being worked on,
 or do you need any help with it?", "reason": "dry-run (confirm not set
 or repo_guard mismatch)"}
```

This is the same category of finding as the anti-hallucination catch in
`ci-flake-triager`: a plausible, well-written model output that didn't
meet a stated, checkable requirement, caught mechanically rather than
trusted on the strength of sounding right.

The pipeline has **not** been run with `--confirm` against any real
repository — deliberately, since posting a real comment (even on my own
repo) wasn't necessary to prove the mechanism works, and running it
against anyone else's repo without being invited to would defeat the
whole point of the safety design.

## What this is NOT

This is not an attempt to solve Kyverno's actual problem (Dependabot
automation, issue triage, scoped test selection, Slack Q&A) — those
require repo-specific context and explicit permission I don't have yet.
This is a demonstration that I can build the *safety pattern* the brief
treats as non-negotiable: kill-switch first, verify-before-trust,
dry-run-by-default, and a durable audit trail — before being handed
write access to anything real.

## How to run it

```bash
export GITHUB_TOKEN=ghp_xxxxxxxx
export GEMINI_API_KEY=AIzaxxxxxxxx

# Enable the agent (it refuses to run otherwise):
# edit .agent-config.yaml -> enabled: true

python3 src/main.py --owner YOUR_GITHUB_USERNAME --repo YOUR_REPO
```

## Tests

```bash
python3 tests/test_safety.py
```
