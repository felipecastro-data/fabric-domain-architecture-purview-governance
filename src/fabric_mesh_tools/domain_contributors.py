"""Domain contributors scope as code: only the groups assigned by Terraform may add workspaces to a domain.

    uv run domain-contributors           # dry run: show domains whose contributors scope differs; exits 1 on drift
    uv run domain-contributors --apply   # restrict them

New domains default to contributorsScope "AllTenant" (an EntireTenant contributor next to the engineers group that
fabric_domain_role_assignments adds). Provider 1.14 has no contributors_scope, and only the preview version of the
Admin API (preview=true) exposes it.
"""

from __future__ import annotations

import argparse

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import FABRIC, request

API = f"{FABRIC}/admin/domains"
DESIRED_SCOPE = "SpecificUsersAndGroups"  # AdminsOnly | AllTenant | SpecificUsersAndGroups


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="restrict the domains that differ")
    args = parser.parse_args(argv)

    domains = terraform.output(terraform.GOVERNANCE_STACK, "domains")
    changes = []
    for key, d in sorted(domains.items()):
        scope = request("GET", f"{API}/{d['id']}?preview=true")["contributorsScope"]
        if scope != DESIRED_SCOPE:
            changes.append((key, d["id"]))
        print(f"{'ok    ' if scope == DESIRED_SCOPE else 'change'}  {key:<10} {scope} -> {DESIRED_SCOPE}")

    if not changes:
        print("Domain contributors scopes match.")
    elif not args.apply:
        raise SystemExit(f"\n{len(changes)} domain(s) differ. Re-run with --apply to update them.")
    else:
        for key, domain_id in changes:
            request("PATCH", f"{API}/{domain_id}?preview=true", {"contributorsScope": DESIRED_SCOPE})
            print(f"updated {key} -> {DESIRED_SCOPE}")


if __name__ == "__main__":
    main()
