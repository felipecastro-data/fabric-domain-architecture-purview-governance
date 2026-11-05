# ADR 0007 — dev → prod environments for the domains stack

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

Until now every merged change went straight to the live mesh. The medallion platform that feeds it already has dev,
test and prod workspaces (`divvy-medallion-dev/-test/-prod`), so a mesh change could be proven against dev data before
it touches prod consumers.

Not everything can have environments. Groups, domains, domain roles and tags are tenant-scope objects: there is one
Fabric tenant, so there is one Mobility domain. Only the domains stack (workspaces, lakehouses, shortcuts, roles) can
be duplicated.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **Terraform CLI workspaces** in one HCP workspace | No new HCP objects | HCP's local-execution workspaces map 1:1 to CLI workspaces anyway; state sharing and permissions can't differ per environment |
| B | **One HCP workspace per environment** (tagged `fabric-mesh-domains`, selected with `TF_WORKSPACE`) and an `environment` variable | Separate state, history and locks per environment; governance shares its outputs with each explicitly; the same code with one variable | `TF_WORKSPACE` must be set for every domains command (Makefile and CI do it) |
| C | **A directory per environment** (`envs/dev`, `envs/prod`) calling a shared module | Explicit; environments can diverge | Duplicated root config that will drift; every change edited twice |
| D | **A second tenant** for dev | True isolation including tenant-scope objects | A second Fabric capacity, Purview licence and Entra tenant; not available on trials |

## Decision

**Option B.** `var.environment` (dev | prod) drives the differences, all in [`environment.tf`](../../infra/terraform/domains/environment.tf):

| | dev | prod |
|---|---|---|
| HCP workspace | `fabric-mesh-domains-dev` | `fabric-mesh-domains` |
| Workspaces | `mesh-<domain>-dev` | `mesh-<domain>` (unchanged) |
| Source | `divvy-medallion-dev` | `divvy-medallion-prod` |
| Endorsement | not checked | Terraform-declared, checked |
| Freshness SLA | not checked | 8 days, alert |

Both environments share the governance stack's groups, domains and tags, so a dev workspace sits in the same domain
as its prod twin, with the same access model. `fabric_domain_workspace_assignments` only tracks the workspaces in its
own configuration (it intersects with the domain's live list), so the two states never fight over a domain.

CI on `main`: governance is applied only when its plan has changes, behind its own `platform` approval (tenant scope).
Then **dev** is applied and checked (tools, workspace domains, data contracts) without approval. **Prod** needs dev to
succeed and a `platform` approval. Every PR gets three plan comments: governance, domains · dev and domains · prod.

## Consequences

- Prod names were kept, so introducing environments planned **no changes** in prod.
- A breaking change is applied to dev first; dev's contract check fails before prod is offered for approval.
- Tenant-scope changes cannot be staged: a governance change reaches both environments when applied. Its separate
  approval is the control.
- Dev lakehouses need their sensitivity label once from a Fabric administrator user
  (`make apply ENV=dev` or `MESH_ENV=dev uv run data-product-governance --apply`), because `bulkSetLabels` rejects
  service principals; until then the dev job reports the label drift.
- **Revisit when:** a test environment is needed (add `test` to the variable's validation and an HCP workspace), or a
  second tenant becomes available for tenant-scope staging (Option D).
