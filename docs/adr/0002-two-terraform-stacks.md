# ADR 0002 — Two Terraform stacks: central governance and domain platform

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

The mesh has two kinds of resources with different owners and blast radii:

- **Tenant scope**: Entra groups, Fabric domains, domain admins and contributors, default sensitivity labels, tenant
  tags. A mistake here affects every domain, and changing it needs Fabric administrator rights.
- **Domain scope**: workspaces, data product lakehouses, workspace roles, shortcuts, OneLake role definitions. Domain
  platform teams change these often.

In a real mesh a central governance team owns the first and domain teams own the second. The repository should show
that split and enforce it, not only describe it.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **One stack** for everything | One plan, one state, simplest CI | A domain change plans (and can destroy) tenant resources. One identity needs every permission. No ownership boundary. |
| B | **One stack per domain** plus a governance stack | Strongest isolation; each domain applies on its own | Three nearly identical stacks and states. Cross-domain shortcuts need a producer's outputs before the consumer's apply, so ordering moves into CI. Overkill for three domains and one maintainer. |
| C | **Two stacks**: `governance` (tenant) → `domains` (all domains), linked through HCP Terraform remote state | Tenant resources can't change from a domain change. Domains read IDs, never write them. One module (`data_product_workspace`) keeps the domain stack DRY. | Two applies in order. Remote state sharing must be configured in HCP. All domains still share one state. |

## Decision

**Option C.** `infra/terraform/governance` is applied first and publishes `domains`, `groups`, `labels`, `tags` and
`tenant_id` as outputs. `infra/terraform/domains` reads them with `terraform_remote_state` and never declares
tenant-scope resources (a rule in [CLAUDE.md](../../CLAUDE.md)). CI applies them in that order behind one approval.

## Consequences

- A domain PR shows a plan for `domains` and an empty plan for `governance`, which makes the scope of a change visible
  in review.
- HCP workspace `fabric-mesh-governance` shares its state only with the domain workspaces.
- Adding a domain touches both stacks: a domain + groups in `governance`, then a data product in `domains`
  (see [design.md](../design.md#onboarding-domain-n)).
- **Revisit when:** domains are owned by different teams with different reviewers. Then split `domains` per domain
  (Option B), with `CODEOWNERS` per directory and a workspace per domain in HCP.
