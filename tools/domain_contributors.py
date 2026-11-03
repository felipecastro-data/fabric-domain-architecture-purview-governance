"""Domain contributors scope as code: only the groups assigned by Terraform may add workspaces to a domain.

python tools/domain_contributors.py           # dry run: show domains whose contributors scope differs
python tools/domain_contributors.py --apply   # restrict them

New domains default to contributorsScope "AllTenant" (an EntireTenant contributor next to the engineers group that
fabric_domain_role_assignments adds). Provider 1.14 has no contributors_scope, and only the preview version of the
Admin API (preview=true) exposes it.
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

API = "https://api.fabric.microsoft.com/v1/admin/domains"
GOVERNANCE_STACK = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "governance"
DESIRED_SCOPE = "SpecificUsersAndGroups"  # AdminsOnly | AllTenant | SpecificUsersAndGroups


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


def main(apply: bool) -> None:
    out = subprocess.run(
        ["terraform", f"-chdir={GOVERNANCE_STACK}", "output", "-json", "domains"],
        check=True, capture_output=True, text=True,
    ).stdout
    domains = json.loads(out)

    changes = []
    for key, d in sorted(domains.items()):
        scope = req("GET", f"{API}/{d['id']}?preview=true")["contributorsScope"]
        mark = "ok    " if scope == DESIRED_SCOPE else "change"
        if scope != DESIRED_SCOPE:
            changes.append((key, d["id"]))
        print(f"{mark}  {key:<10} {scope} -> {DESIRED_SCOPE}")

    if not changes:
        print("Domain contributors scopes match.")
    elif not apply:
        print(f"\n{len(changes)} domain(s) differ. Re-run with --apply to update them.")
    else:
        for key, domain_id in changes:
            req("PATCH", f"{API}/{domain_id}?preview=true", {"contributorsScope": DESIRED_SCOPE})
            print(f"updated {key} -> {DESIRED_SCOPE}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv[1:])
