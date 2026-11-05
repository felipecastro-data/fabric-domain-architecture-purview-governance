# ADR 0003 — OneLake security roles: Terraform role map applied by a Python upsert

- **Status:** Accepted (temporary, until the provider fix ships)
- **Date:** 2026-11-03

## Context

OneLake security roles decide which tables a consumer can read through the shortcut chain. They must be code, reviewed
in PRs and checked for drift like everything else.

The provider resource `fabric_onelake_data_access_security` (microsoft/fabric 1.14) creates the roles, then fails with
"inconsistent result after apply" whenever a member is an Entra group: the API never returns `objectType`, so every
apply ends in an error and tainted state
([microsoft/terraform-provider-fabric#1044](https://github.com/microsoft/terraform-provider-fabric/issues/1044)).

The REST API has two write paths: `PUT …/dataAccessRoles` replaces **all** roles on an item, and `POST` creates or
updates a single role.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **Provider resource** anyway, with `lifecycle { ignore_changes }` | Pure Terraform | Every apply still errors and taints the resource. Ignoring members hides the drift we want to catch. |
| B | **Portal**, documented with screenshots | Nothing to build | Not reviewable, not reproducible, no drift check |
| C | **`PUT` replace-all** from a script | One call per item | Deletes roles this repo doesn't own (for example on the shared `lh_gold` in the medallion workspace) |
| D | **Role map in Terraform, applied by `tools/onelake_roles.py` with single-role `POST`** | Terraform stays the source of truth and validates the map. Only managed roles are touched; unmanaged roles are listed, not deleted. Dry run + exit 1 on drift gives a compliance check. | A second tool to maintain. Deleting a role removed from the map is manual. |

## Decision

**Option D.** `var.access_roles` is validated in Terraform (no table-level roles on shortcut lakehouses) and rendered as
API bodies in the `onelake_access_roles` output. `onelake_roles.py` compares each role order-insensitively, ignoring
`objectType`, and upserts only the ones that differ. A `removed { destroy = false }` block forgot the tainted resources
without deleting the live roles.

## Consequences

- The apply job runs the tool after `terraform apply`; the compliance job runs it as a dry run daily.
- A role deleted from the map stays in Fabric and is reported as `unmanaged` until someone removes it.
- **Revisit when:** #1044 ships. Then import the roles into `fabric_onelake_data_access_security`, delete the tool and
  this ADR's status becomes Superseded.
