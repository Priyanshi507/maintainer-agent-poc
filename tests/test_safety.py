import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from config import load_config, enforce_kill_switch, AgentDisabledError, AgentConfig
from pr_ingest import _days_since, OpenPR, filter_stale
from draft_action import _verify_draft_facts, DraftError


def test_missing_config_defaults_to_disabled():
    """No .agent-config.yaml at all -> agent must refuse to run, not
    silently proceed. This is the single most important test: an agent
    that fails open (runs when it can't find its safety config) is
    unsafe by construction."""
    config = load_config(path="/tmp/definitely_does_not_exist.yaml")
    assert config.enabled is False
    try:
        enforce_kill_switch(config)
        print("FAIL: kill-switch did not block a missing config")
        raise SystemExit(1)
    except AgentDisabledError:
        print("PASS: missing config correctly defaults to disabled and blocks the run")


def test_explicit_disabled_blocks():
    config = AgentConfig(enabled=False)
    try:
        enforce_kill_switch(config)
        print("FAIL: explicit enabled=False did not block")
        raise SystemExit(1)
    except AgentDisabledError:
        print("PASS: explicit enabled=False correctly blocks the run")


def test_explicit_enabled_passes():
    config = AgentConfig(enabled=True)
    enforce_kill_switch(config)  # should not raise
    print("PASS: explicit enabled=True correctly allows the run to proceed")


def test_days_since_math():
    """Pure function test for the staleness calculation the whole
    pipeline depends on."""
    from datetime import datetime, timezone, timedelta
    ten_days_ago = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat().replace("+00:00", "Z")
    result = _days_since(ten_days_ago)
    assert result in (9, 10, 11), f"Expected ~10 days, got {result}"
    print(f"PASS: days_since correctly computed as {result} for a 10-day-old timestamp")


def test_filter_stale():
    prs = [
        OpenPR(1, "fresh", "http://x/1", "2026-01-01T00:00:00Z", days_since_update=2, author="a"),
        OpenPR(2, "stale", "http://x/2", "2026-01-01T00:00:00Z", days_since_update=20, author="b"),
    ]
    stale = filter_stale(prs, threshold_days=14)
    assert len(stale) == 1 and stale[0].number == 2
    print("PASS: filter_stale correctly separates fresh from stale PRs")


def test_draft_missing_pr_number_rejected():
    """The critical anti-hallucination case for this project: a drafted
    comment that doesn't even mention the PR number it's supposedly
    about must be rejected mechanically."""
    pr = OpenPR(42, "some title", "http://x/42", "2026-01-01T00:00:00Z", days_since_update=15, author="alice")
    bad_body = "Hey, this PR looks stale, is it still being worked on?"  # no PR number, no day count
    try:
        _verify_draft_facts(bad_body, pr)
        print("FAIL: draft missing PR facts was NOT rejected")
        raise SystemExit(1)
    except DraftError:
        print("PASS: drafted comment missing verifiable PR facts correctly rejected")


def test_draft_with_correct_facts_passes():
    pr = OpenPR(42, "some title", "http://x/42", "2026-01-01T00:00:00Z", days_since_update=15, author="alice")
    good_body = "Hi! PR #42 hasn't seen activity in 15 days - is it still being worked on?"
    _verify_draft_facts(good_body, pr)  # should not raise
    print("PASS: drafted comment with correct verifiable facts accepted")


if __name__ == "__main__":
    test_missing_config_defaults_to_disabled()
    test_explicit_disabled_blocks()
    test_explicit_enabled_passes()
    test_days_since_math()
    test_filter_stale()
    test_draft_missing_pr_number_rejected()
    test_draft_with_correct_facts_passes()
    print("\nAll tests passed.")
