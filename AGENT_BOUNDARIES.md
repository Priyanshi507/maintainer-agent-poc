# Safe Automation Boundaries — Template

The Kyverno AI Assistant brief (issue #16665) calls for an explicit
"safe automation boundaries" document as a Phase 0 deliverable: *"which
paths/files an agent may modify autonomously... vs never touch without
human review."* This file is a generic template for that reasoning,
applied to this prototype rather than to kyverno/kyverno directly
(consistent with not building against the live repo before the term
begins) — but the classification logic itself is meant to generalize.

## The core distinction

Not all repository changes carry the same risk if an agent gets them
wrong. The boundary isn't really "which files" — it's **how expensive
a mistake is to detect and undo**, which depends on three properties:

1. **Reversibility** — can a human trivially undo this (delete a
   comment, remove a label) or does undoing it require real effort
   (a merged commit, a closed issue, a triggered release)?
2. **Blast radius** — does a mistake affect one PR/issue, or does it
   affect the build, CI, or every future contributor?
3. **Verifiability before action** — can the agent's claim be checked
   against ground truth mechanically (a quoted log line, a PR number)
   before acting, or does it require human judgment no config file can
   encode (is this API change actually breaking, is this bug report a
   duplicate)?

## Applying it to this prototype

| Action | Reversibility | Blast radius | Verifiable pre-action? | Boundary |
|---|---|---|---|---|
| Draft a nudge comment (dry-run) | Trivial (nothing happened) | None | Yes — mechanically checked against real PR data | Fully autonomous |
| Post a nudge comment (real) | Easy (delete comment) | One PR, cosmetic | Yes, same check | Autonomous, but gated behind explicit `--confirm` + exact `--repo-guard` match |
| Auto-merge a dependency bump | Hard (already in history) | Whole build, every downstream user | Partially — CI passing is verifiable, "no breaking-change signal" is not | **Never autonomous in this prototype's scope** — would require a human-defined allowlist of what "safe to auto-merge" means, which this prototype does not attempt |
| Classify/label an issue | Easy (remove label) | Low — affects triage queue, not code | No — requires reading intent, not just matching a pattern | Not implemented; if built, would need a confidence threshold with mandatory human review below it, same principle as this prototype's `UNKNOWN` category in the related `ci-flake-triager` project |

## Why this prototype only implements one row

This project deliberately implements only the top row (comment drafting,
dry-run by default) rather than attempting the harder rows (auto-merge,
issue classification) as a real, working feature. The reasoning: those
harder cases don't have a clean mechanical verification story the way a
PR-number-and-day-count check does — and per the table above, actions
without a "verifiable before action" property are exactly the ones that
shouldn't be automated confidently. Building a fake version of them
would demonstrate the wrong instinct for a project whose entire premise
is "guardrails first."
