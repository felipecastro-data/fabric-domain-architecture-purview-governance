# ADR 0004 — PR plans run with the deployment identity (accepted risk)

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

Every PR gets a `terraform plan` comment per stack, and the `compliance` check reads live tenant state. Both need
credentials: OIDC to Entra (Fabric, Graph) and the HCP Terraform token for remote state.

Providers and data sources can run code during `terraform plan`, and a PR controls the code being planned. Whoever can
open a PR from a branch of this repository can therefore act with the identity the plan uses, before any approval.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **No plan on PRs**; plan only on `main` behind the approval | No credentials reach PR code | Reviewers approve a diff without seeing what it does to the tenant. Drift is found after merge. |
| B | **A separate read-only identity for plans**: Viewer on the mesh workspaces, read-only admin APIs, `Group.Read.All`; the write identity only in the `platform` environment | Least privilege; a malicious plan can only read | A second Entra app and federated credentials, a second set of workspace roles, and providers that need write scopes to refresh some resources. More moving parts than the threat justifies for one maintainer. |
| C | **One identity**, PR plans only for branches of this repository; fork PRs get no credentials | Simple; reviewers see real plans | A write-access contributor's PR runs with the deployment identity before approval |

## Decision

**Option C**, as a deliberate simplification for a single maintainer. Fork PRs are skipped by job conditions (and
GitHub never gives them secrets or OIDC tokens), which also satisfies the required checks. The write path stays gated:
`apply` runs only on `main`, in the `platform` environment with a required reviewer.

## Consequences

- The risk is limited to people who already have write access to the repository.
- The CI identity's reach is kept small: Admin of the mesh workspaces only through their owners groups, Member of the
  source workspace, Fabric admin APIs through one automation group. Its Graph permissions are tenant-wide because Graph
  has no per-group application scope (see [design.md](../design.md#4-security)).
- **Revisit when:** a second person gets write access. Then implement Option B and restrict the write identity's
  federated credential to `environment:platform`.
