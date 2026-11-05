"""Workspace domain assignments, checked: every data product workspace sits in the domain Terraform assigned it to,
and no unmanaged workspace uses the data product name prefix.

    uv run workspace-domains   # check only; exits 1 on drift

Terraform (fabric_domain_workspace_assignments) makes the assignments. Tenant and domain admins may reassign
workspaces in the portal, and new workspaces may be created outside Terraform, so CI checks the live state.
"""

from __future__ import annotations

import argparse
import urllib.parse

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import FABRIC, request

API = f"{FABRIC}/admin/workspaces"


def diff_assignments(desired: dict[str, dict], prefix: str, live: dict[str, dict]) -> list[tuple[str, str]]:
    """[(status, message)] per managed workspace and per unmanaged workspace that uses the prefix."""
    managed = {w["workspace_id"] for w in desired.values()}
    lines = []
    for key, w in sorted(desired.items()):
        current = live.get(w["workspace_id"], {}).get("domainId")
        lines.append(("ok" if current == w["domain_id"] else "DRIFT", f"{key:<10} {current} -> {w['domain_id']}"))
    for ws_id, w in sorted(live.items(), key=lambda kv: kv[1]["name"]):
        if w["name"].startswith(prefix) and ws_id not in managed:
            lines.append(("DRIFT", f"unmanaged workspace {w['name']} ({ws_id}), domain {w.get('domainId')}"))
    return lines


def active_workspaces() -> dict[str, dict]:
    workspaces, url = [], f"{API}?type=Workspace&state=Active"
    while url:
        page = request("GET", url)
        workspaces += page["workspaces"]
        token = page.get("continuationToken")
        url = f"{API}?continuationToken={urllib.parse.quote(token)}" if token else None
    return {w["id"]: w for w in workspaces}


def main(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    lines = diff_assignments(
        terraform.output(terraform.DOMAINS_STACK, "workspaces"),
        terraform.output(terraform.DOMAINS_STACK, "workspace_prefix"),
        active_workspaces(),
    )
    for status, message in lines:
        print(f"{status:<6}  {message}")
    drift = [m for s, m in lines if s != "ok"]
    if drift:
        raise SystemExit(f"\n{len(drift)} workspace(s) differ from Terraform.")
    print("Workspace domain assignments match Terraform.")


if __name__ == "__main__":
    main()
