"""Domain contributors as code: no tenant-wide contributor, only the groups assigned by Terraform.

    uv run domain-contributors           # dry run: show domains with a tenant-wide contributor; exits 1 on drift
    uv run domain-contributors --apply   # remove it

A domain whose contributors are "the entire organization" lets anyone add a workspace to it. The preview Admin API
exposed that as contributorsScope; it was retired, and the stable API models it as a Contributor role assignment to an
EntireTenant principal. fabric_domain_role_assignments adds the engineers group but leaves other principals alone,
so this tool removes the tenant-wide one.
"""

from __future__ import annotations

import argparse

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import FABRIC, request

API = f"{FABRIC}/admin/domains"


def tenant_wide_contributors(assignments: list[dict]) -> list[dict]:
    """The EntireTenant principals among a domain's Contributor role assignments."""
    return [
        {"id": a["principal"]["id"], "type": "EntireTenant"}
        for a in assignments
        if a["role"] == "Contributor" and a["principal"]["type"] == "EntireTenant"
    ]


def role_assignments(domain_id: str) -> list[dict]:
    assignments, url = [], f"{API}/{domain_id}/roleAssignments"
    while url:
        page = request("GET", url)
        assignments += page.get("value", [])
        url = page.get("continuationUri")
    return assignments


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="remove tenant-wide contributors")
    args = parser.parse_args(argv)

    domains = terraform.output(terraform.GOVERNANCE_STACK, "domains")
    changes = []
    for key, d in sorted(domains.items()):
        extra = tenant_wide_contributors(role_assignments(d["id"]))
        if extra:
            changes.append((key, d["id"], extra))
        print(f"{'change' if extra else 'ok    '}  {key:<10} tenant-wide contributor: {'yes' if extra else 'no'}")

    if not changes:
        print("Domain contributors match.")
    elif not args.apply:
        raise SystemExit(f"\n{len(changes)} domain(s) differ. Re-run with --apply to update them.")
    else:
        for key, domain_id, principals in changes:
            request(
                "POST",
                f"{API}/{domain_id}/roleAssignments/bulkUnassign",
                {"type": "Contributor", "principals": principals},
            )
            print(f"updated {key}: tenant-wide contributor removed")


if __name__ == "__main__":
    main()
