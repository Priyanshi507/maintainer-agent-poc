"""
config.py

Implements the guardrail the Kyverno AI Maintainer Assistant brief calls
out explicitly as "required, not optional":

    "Rate-limited and kill-switch controlled (label or repo variable to
    pause the bot instantly)."
    "Humans can override or disable per-repo/per-workflow via a config
    file (e.g., .github/ai-maintainer.yaml)."

This module is deliberately the first thing built and the first thing
checked on every run - an agent that reads its kill-switch after it's
already taken an action isn't actually safe, it's just documented as
unsafe. The check has to be structurally first, not just conventionally
first.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

import yaml


class AgentDisabledError(RuntimeError):
    """Raised when the config file's kill-switch is active. This is not
    an error condition to catch and route around - callers should let
    it propagate and stop the run entirely."""
    pass


@dataclass
class AgentConfig:
    enabled: bool = True
    max_actions_per_run: int = 5
    allowed_actions: list[str] = field(default_factory=lambda: ["comment_draft"])
    stale_pr_days_threshold: int = 14


def load_config(path: str = ".agent-config.yaml") -> AgentConfig:
    """
    Loads the kill-switch config. If the file doesn't exist, the agent
    defaults to DISABLED, not enabled - an agent that runs by default
    when it can't find its own safety config is the wrong default for
    something with write-adjacent capability. The config file must
    explicitly opt in.
    """
    if not os.path.exists(path):
        return AgentConfig(enabled=False)

    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}

    return AgentConfig(
        enabled=raw.get("enabled", False),
        max_actions_per_run=raw.get("max_actions_per_run", 5),
        allowed_actions=raw.get("allowed_actions", ["comment_draft"]),
        stale_pr_days_threshold=raw.get("stale_pr_days_threshold", 14),
    )


def enforce_kill_switch(config: AgentConfig) -> None:
    if not config.enabled:
        raise AgentDisabledError(
            "Agent is disabled (config missing, or enabled: false in "
            ".agent-config.yaml). Refusing to run. This check happens "
            "before any GitHub API calls that could take action."
        )
