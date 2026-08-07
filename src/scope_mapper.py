"""
scope_mapper.py

Implements the brief's Phase 2 deliverable in generic form:

    "Scoped test selection: analyze the diff (changed packages/dirs)
    and trigger only the relevant subset of unit/conformance tests
    instead of the full suite."

This is deliberately built as a general, config-driven mapper rather
than hardcoded to this prototype's own two source files - the point is
to demonstrate the mapping *mechanism*, which is what would need to
generalize to Kyverno's much larger pkg/ tree, not to solve test
selection for a two-file toy project (which wouldn't need it).

Design note, informed by omlahore's real analysis on issue #16665
(before the thread was locked): a path-based map is not sound on its
own for every case - some source files are tested indirectly by sibling
packages, and some paths (generated code) shouldn't be treated as
selection targets at all, they need a different action (regenerate +
verify) rather than "find and run a unit test." This mapper's schema
reflects that distinction explicitly (see `action` field) rather than
assuming every path maps 1:1 to a runnable test.
"""

from __future__ import annotations

import fnmatch
import json
from dataclasses import dataclass, asdict
from typing import Literal

ActionType = Literal["run_tests", "regenerate_and_verify", "no_action_defined"]


@dataclass
class ScopeRule:
    path_pattern: str          # glob-style, e.g. "src/*.py"
    action: ActionType
    test_targets: list[str]    # test files/commands to run, if action == run_tests
    note: str = ""


@dataclass
class ScopeResult:
    changed_path: str
    matched_rule: str | None
    action: ActionType
    test_targets: list[str]


# Example mapping for THIS repo's own structure - demonstrates the
# mechanism against real paths, not a hypothetical.
EXAMPLE_SCOPE_MAP: list[ScopeRule] = [
    ScopeRule(
        path_pattern="src/config.py",
        action="run_tests",
        test_targets=["tests/test_safety.py::test_missing_config_defaults_to_disabled",
                       "tests/test_safety.py::test_explicit_disabled_blocks",
                       "tests/test_safety.py::test_explicit_enabled_passes"],
        note="Kill-switch logic - narrowest, highest-priority test subset.",
    ),
    ScopeRule(
        path_pattern="src/pr_ingest.py",
        action="run_tests",
        test_targets=["tests/test_safety.py::test_days_since_math",
                       "tests/test_safety.py::test_filter_stale"],
    ),
    ScopeRule(
        path_pattern="src/draft_action.py",
        action="run_tests",
        test_targets=["tests/test_safety.py::test_draft_missing_pr_number_rejected",
                       "tests/test_safety.py::test_draft_with_correct_facts_passes"],
        note="Anti-hallucination check - the highest-value test subset if this file changes.",
    ),
    ScopeRule(
        path_pattern="*.jsonl",
        action="no_action_defined",
        test_targets=[],
        note="Runtime output (audit log), not source - no test should be selected for this.",
    ),
    ScopeRule(
        path_pattern="README.md",
        action="no_action_defined",
        test_targets=[],
        note="Documentation-only change - correctly maps to nothing, not a fallback to full suite.",
    ),
]


def map_changed_paths(changed_paths: list[str], scope_map: list[ScopeRule] = EXAMPLE_SCOPE_MAP) -> list[ScopeResult]:
    """
    For each changed file path, find the first matching rule (by glob
    pattern) and return what action it implies. Unmatched paths get
    action="no_action_defined" rather than silently defaulting to
    "run everything" - an unmapped path should be visible as a gap in
    the map, not hidden behind a safe-seeming fallback.
    """
    results = []
    for path in changed_paths:
        matched = None
        for rule in scope_map:
            if fnmatch.fnmatch(path, rule.path_pattern):
                matched = rule
                break
        if matched:
            results.append(ScopeResult(
                changed_path=path,
                matched_rule=matched.path_pattern,
                action=matched.action,
                test_targets=matched.test_targets,
            ))
        else:
            results.append(ScopeResult(
                changed_path=path,
                matched_rule=None,
                action="no_action_defined",
                test_targets=[],
            ))
    return results


if __name__ == "__main__":
    # Demonstration against a realistic changed-file set for this repo.
    example_diff = ["src/draft_action.py", "README.md", "agent_audit_log.jsonl", "src/unknown_new_file.py"]
    results = map_changed_paths(example_diff)
    print(json.dumps([asdict(r) for r in results], indent=2))
