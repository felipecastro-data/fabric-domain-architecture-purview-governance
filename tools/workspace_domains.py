"""Workspace domain assignments, checked: every data product workspace (name prefix from the domains stack) sits in
the domain Terraform assigned it to, and no other workspace uses the prefix.

python tools/workspace_domains.py   # check only; exits 1 on drift

Terraform (fabric_domain_workspace_assignments) makes the assignments. Tenant and domain admins may reassign
workspaces in the portal, and new workspaces may be created outside Terraform, so CI checks the live state.
"""

from __future__ import annotations

import json
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from fabric_auth import access_token  # fresh GitHub OIDC exchange in CI, az CLI locally

API = "https://api.fabric.microsoft.com/v1/admin/workspaces"
DOMAINS_STACK = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "domains"


def req(method: str, url: str) -> dict:
    headers = {"Authorization": f"Bearer {access_token()}"}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method=method, headers=headers), timeout=60) as r:  # noqa: S310
                return json.loads(r.read())
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {url} -> {exc.code} {exc.read().decode()}") from exc
        except urllib.error.URLError:  # transient connection failures; HTTP errors are never retried
            if attempt == 2:
                raise
            time.sleep(5)
    raise AssertionError("unreachable")


def tf_output(name: str):
    out = subprocess.run(
        ["terraform", f"-chdir={DOMAINS_STACK}", "output", "-json", name],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def active_workspaces() -> list[dict]:
    workspaces, url = [], f"{API}?type=Workspace&state=Active"
    while url:
        page = req("GET", url)
        workspaces += page["workspaces"]
        token = page.get("continuationToken")
        url = f"{API}?continuationToken={urllib.parse.quote(token)}" if token else None
    return workspaces


def main() -> None:
    desired = {w["workspace_id"]: (key, w["domain_id"]) for key, w in tf_output("workspaces").items()}
    prefix = tf_output("workspace_prefix")
    live = {w["id"]: w for w in active_workspaces()}

    drift = []
    for ws_id, (key, domain_id) in sorted(desired.items(), key=lambda d: d[1][0]):
        current = live.get(ws_id, {}).get("domainId")
        ok = current == domain_id
        print(f"{'ok    ' if ok else 'DRIFT '}  {key:<10} {current} -> {domain_id}")
        if not ok:
            drift.append(key)
    for ws_id, w in sorted(live.items(), key=lambda w: w[1]["name"]):
        if w["name"].startswith(prefix) and ws_id not in desired:
            print(f"DRIFT   unmanaged workspace {w['name']} ({ws_id}), domain {w.get('domainId')}")
            drift.append(w["name"])

    if drift:
        raise SystemExit(f"\n{len(drift)} workspace(s) differ from Terraform: {', '.join(drift)}")
    print("Workspace domain assignments match Terraform.")


if __name__ == "__main__":
    main()
