"""OneLake security roles as code: applies the roles rendered by the domains stack (output `onelake_access_roles`).

python tools/onelake_roles.py           # dry run: show which roles differ from Terraform; exits 1 on drift
python tools/onelake_roles.py --apply   # create or update the ones that differ

Each role is upserted on its own (POST .../dataAccessRoles), never the replace-all PUT, so roles this repo doesn't
manage are left alone and only reported. Stand-in for fabric_onelake_data_access_security until
microsoft/terraform-provider-fabric#1044 is released.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from fabric_auth import access_token  # fresh GitHub OIDC exchange in CI, az CLI locally

API = "https://api.fabric.microsoft.com/v1"
DOMAINS_STACK = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "domains"


def req(method: str, url: str, body: dict | None = None) -> dict | None:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"}
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=60) as r:  # noqa: S310
                raw = r.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {url} -> {exc.code} {exc.read().decode()}") from exc
        except urllib.error.URLError:  # transient connection failures; HTTP errors are never retried
            if attempt == 2:
                raise
            time.sleep(5)
    return None


def desired_roles() -> dict[str, dict]:
    out = subprocess.run(
        ["terraform", f"-chdir={DOMAINS_STACK}", "output", "-json", "onelake_access_roles"],
        check=True, capture_output=True, text=True,
    ).stdout
    return json.loads(out)


def normalize(role: dict) -> dict:
    """Comparable form of a role: order-insensitive, and without objectType (the API never returns it)."""
    members = role.get("members", {})
    return {
        "rules": sorted(
            (rule["effect"], sorted((p["attributeName"], tuple(sorted(p["attributeValueIncludedIn"]))) for p in rule["permission"]))
            for rule in role["decisionRules"]
        ),
        "entra": sorted((m["objectId"], m["tenantId"]) for m in members.get("microsoftEntraMembers", [])),
        "items": sorted((m["sourcePath"], tuple(sorted(m["itemAccess"]))) for m in members.get("fabricItemMembers", [])),
    }


def main(apply: bool) -> None:
    desired = desired_roles()
    items = {(r["workspace_id"], r["item_id"]) for r in desired.values()}
    current = {
        item: {r["name"]: r for r in req("GET", f"{API}/workspaces/{item[0]}/items/{item[1]}/dataAccessRoles")["value"]}
        for item in sorted(items)
    }

    changes = {}
    for key, r in sorted(desired.items()):
        existing = current[(r["workspace_id"], r["item_id"])].get(r["role"]["name"])
        if existing is None:
            state = "create"
        elif normalize(existing) != normalize(r["role"]):
            state = "update"
        else:
            state = "ok    "
        if state != "ok    ":
            changes[key] = r
        print(f"{state}  {key}")

    managed = {(r["workspace_id"], r["item_id"], r["role"]["name"]) for r in desired.values()}
    for (ws, item), roles in current.items():
        for name in roles:
            if (ws, item, name) not in managed:
                print(f"unmanaged  {ws}/{item}.{name}")

    if not changes:
        print("OneLake roles match Terraform.")
    elif not apply:
        raise SystemExit(f"\n{len(changes)} role(s) differ. Re-run with --apply to update them.")
    else:
        for key, r in changes.items():
            req("POST", f"{API}/workspaces/{r['workspace_id']}/items/{r['item_id']}/dataAccessRoles", r["role"])
            print(f"applied {key}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv[1:])
