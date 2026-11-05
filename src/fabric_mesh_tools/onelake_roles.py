"""OneLake security roles as code: applies the roles rendered by the domains stack (output `onelake_access_roles`).

    uv run onelake-roles           # dry run: show which roles differ from Terraform; exits 1 on drift
    uv run onelake-roles --apply   # create or update the ones that differ

Each role is upserted on its own (POST .../dataAccessRoles), never the replace-all PUT, so roles this repo doesn't
manage are left alone and only reported. Stand-in for fabric_onelake_data_access_security until
microsoft/terraform-provider-fabric#1044 is released (docs/adr/0003).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import FABRIC, request


def normalize(role: dict) -> dict:
    """Comparable form of a role: order-insensitive, and without objectType (the API never returns it)."""
    members = role.get("members", {})
    return {
        "rules": sorted(
            (
                rule["effect"],
                sorted((p["attributeName"], tuple(sorted(p["attributeValueIncludedIn"]))) for p in rule["permission"]),
            )
            for rule in role["decisionRules"]
        ),
        "entra": sorted((m["objectId"], m["tenantId"]) for m in members.get("microsoftEntraMembers", [])),
        "items": sorted(
            (m["sourcePath"], tuple(sorted(m["itemAccess"]))) for m in members.get("fabricItemMembers", [])
        ),
    }


@dataclass
class Plan:
    states: dict[str, str] = field(default_factory=dict)  # role key => "ok" | "create" | "update"
    unmanaged: list[str] = field(default_factory=list)  # "<workspace>/<item>.<role>" not in Terraform

    @property
    def changes(self) -> list[str]:
        return [k for k, s in self.states.items() if s != "ok"]


def plan(desired: dict[str, dict], current: dict[tuple[str, str], dict[str, dict]]) -> Plan:
    """Compare Terraform's roles with the live roles per (workspace, item)."""
    result = Plan()
    for key, r in sorted(desired.items()):
        existing = current.get((r["workspace_id"], r["item_id"]), {}).get(r["role"]["name"])
        if existing is None:
            result.states[key] = "create"
        elif normalize(existing) != normalize(r["role"]):
            result.states[key] = "update"
        else:
            result.states[key] = "ok"
    managed = {(r["workspace_id"], r["item_id"], r["role"]["name"]) for r in desired.values()}
    for (ws, item), roles in sorted(current.items()):
        result.unmanaged += [f"{ws}/{item}.{name}" for name in sorted(roles) if (ws, item, name) not in managed]
    return result


def live_roles(items: set[tuple[str, str]]) -> dict[tuple[str, str], dict[str, dict]]:
    return {
        (ws, item): {
            r["name"]: r for r in request("GET", f"{FABRIC}/workspaces/{ws}/items/{item}/dataAccessRoles")["value"]
        }
        for ws, item in sorted(items)
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="create or update the roles that differ")
    args = parser.parse_args(argv)

    desired = terraform.output(terraform.DOMAINS_STACK, "onelake_access_roles")
    result = plan(desired, live_roles({(r["workspace_id"], r["item_id"]) for r in desired.values()}))
    for key, state in result.states.items():
        print(f"{state:<6}  {key}")
    for name in result.unmanaged:
        print(f"unmanaged  {name}")

    if not result.changes:
        print("OneLake roles match Terraform.")
    elif not args.apply:
        raise SystemExit(f"\n{len(result.changes)} role(s) differ. Re-run with --apply to update them.")
    else:
        for key in result.changes:
            r = desired[key]
            request("POST", f"{FABRIC}/workspaces/{r['workspace_id']}/items/{r['item_id']}/dataAccessRoles", r["role"])
            print(f"applied {key}")


if __name__ == "__main__":
    main()
