"""Desired state comes from the Terraform stacks' outputs, so the tools and Terraform share one source of truth.

The domains stack has one state per environment (HCP workspaces tagged ``fabric-mesh-domains``). ``MESH_ENV``
(dev | prod, default prod) picks it; the governance stack is tenant-scope and has a single state.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GOVERNANCE_STACK = ROOT / "infra" / "terraform" / "governance"
DOMAINS_STACK = ROOT / "infra" / "terraform" / "domains"
DOMAINS_WORKSPACES = {"prod": "fabric-mesh-domains", "dev": "fabric-mesh-domains-dev"}


def environment() -> str:
    env = os.environ.get("MESH_ENV", "prod")
    if env not in DOMAINS_WORKSPACES:
        raise SystemExit(f"MESH_ENV must be one of {', '.join(DOMAINS_WORKSPACES)}, not {env!r}")
    return env


def stack_env(stack: Path) -> dict[str, str]:
    """Process environment for a terraform command: TF_WORKSPACE for the domains stack, none for governance
    (its cloud block names its only workspace, and a different TF_WORKSPACE would be an error)."""
    env = {k: v for k, v in os.environ.items() if k != "TF_WORKSPACE"}
    if stack == DOMAINS_STACK:
        env["TF_WORKSPACE"] = DOMAINS_WORKSPACES[environment()]
    return env


def output(stack: Path, name: str):
    """``terraform output -json <name>`` of an initialised stack (the domains stack in ``MESH_ENV``)."""
    cmd = ["terraform", f"-chdir={stack}", "output", "-json", name]
    return json.loads(subprocess.run(cmd, check=True, capture_output=True, text=True, env=stack_env(stack)).stdout)
