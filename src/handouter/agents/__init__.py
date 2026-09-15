"""Agent interaction layer.

`manual` prepares a portable GUI/Web-agent handoff bundle; CLI adapters can run
supported local coding agents non-interactively against the same handoff.
"""

from .base import AgentAvailability, AgentRunResult
from .manual import ManualBundleResult, create_manual_bundle
from .runner import available_cli_agents, run_cli_agent

__all__ = [
    "AgentAvailability",
    "AgentRunResult",
    "ManualBundleResult",
    "available_cli_agents",
    "create_manual_bundle",
    "run_cli_agent",
]
