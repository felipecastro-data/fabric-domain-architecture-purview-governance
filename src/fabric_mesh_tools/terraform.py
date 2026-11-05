"""Desired state comes from the Terraform stacks' outputs, so the tools and Terraform share one source of truth."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_STACK = ROOT / "infra" / "terraform" / "governance"
DOMAINS_STACK = ROOT / "infra" / "terraform" / "domains"


def output(stack: Path, name: str):
    """``terraform output -json <name>`` of an initialised stack."""
    cmd = ["terraform", f"-chdir={stack}", "output", "-json", name]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True).stdout)  # noqa: S603
