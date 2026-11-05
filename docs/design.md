# Design: scalability, cost, governance and security

How the mesh behaves today, what it costs, who owns and can reach what, and what changes as it grows. The reasoning
behind the main choices is in the [architecture decision records](adr/).

Figures are from the live tenant on 2026-11-05 unless stated otherwise. Platform limits are from the Microsoft Fabric
documentation at that date; check the linked pages before relying on them.

## 1. Scalability

### Current size

| | Count | Limit that matters |
|---|---:|---|
| Domains | 3 | — |
| Entra groups | 9 (3 per domain) | — |
| Data product lakehouses | 3 | — |
| Shortcuts | 12 (7 to the source, 5 cross-domain) | 100,000 per item |
| Longest shortcut chain | 2 hops (`lh_analytics` → `lh_mobility` → `lh_gold`) | 10 shortcuts per OneLake path; 5 direct shortcuts to shortcut links |
| OneLake roles | 6 (2 on mesh lakehouses, 4 on source lakehouses) | 250 roles per item (1,000 on request) |
| Members of the largest role | 4 groups (`lh_gold.MeshWeather`) | 500 users or groups per role |
| Terraform resources | 57 in prod (2 stacks) + 32 in dev | — |
| Environments | dev, prod (domains stack); governance shared | — |

Limits: [OneLake shortcuts](https://learn.microsoft.com/fabric/onelake/onelake-shortcuts),
[OneLake security](https://learn.microsoft.com/fabric/onelake/security/data-access-control-model).

### Onboarding domain N

Adding a domain is data, not code:

1. `governance`: one entry in `var.domains` (name, kind, default label). Terraform creates 3 groups, the domain, its
   admins and contributors.
2. `domains`: one entry in `var.data_products` (lakehouse, tags, endorsement, shortcuts) and, if it reads upstream
   tables, its groups in `var.access_roles`. The `data_product_workspace` module creates the workspace, roles,
   lakehouse and domain assignment.
3. A data contract: `uv run --extra onelake data-contracts --scaffold <domain> > contracts/<domain>.yml`, then add
   descriptions, keys, classification and owners.
4. Merge: CI applies governance, then the domain in dev (checked against its contract), then prod after approval; the
   compliance checks cover it from their next run.

Every check loops over Terraform outputs, so no tool changes.

### What grows with N domains

| Grows | How | Pressure point |
|---|---|---|
| Groups | 3 N | Entra has no practical limit here; group sprawl is a governance problem, not a platform one |
| Roles on the source lakehouses | constant (one role per access tier) | Members per role grow by 1–2 groups per domain: 500 per role allows about 250 domains per tier |
| Roles on producer lakehouses | 1 per producer (`CrossDomainRead`) | Members grow with the number of consumer domains |
| Shortcut chain depth | +1 per consumer-of-a-consumer layer | Max 5 direct shortcuts to shortcut links. A third tier (a consumer reading Analytics) still fits; deeper reuse should materialize a product instead (ADR 0001) |
| Compliance run | One scanner call for all workspaces, one GET per item and role | Linear and small: about 30–50 s today, dominated by `terraform init` |
| State size | One `domains` state for all domains | Plan time and blast radius grow with every domain. Split per domain when teams diverge (ADR 0002) |

### Read path

Every read goes through the chain to the original Delta files; nothing is cached or copied. Reading all 6,006,901
rows of `fact_trips` took a median 13.0 s directly from `lh_gold` and 13.0 s through two hops from `lh_analytics`
(delta-rs on a laptop, 3 runs each after a warm-up); resolving the extra shortcuts added about 0.7 s to opening the
table. Hops cost metadata lookups, not data transfer.

## 2. Cost

### Today (trial)

| Item | SKU | Cost |
|---|---|---|
| Fabric capacity | Trial `FTL64` (West US), shared with the medallion platform and both environments | 0 until the trial ends (2026-12-12) |
| Purview Information Protection | Microsoft 365 E5 Information Protection & Governance trial, 25 seats | 0 until 2026-12-03 |
| HCP Terraform | Free tier, local execution | 0 |
| GitHub Actions | Public repository | 0 |

### Replacing the trial

List prices (pay-as-you-go, US regions, 2026); reservations cut capacity cost by about 40%.

| Item | Choice | Why | Order of magnitude |
|---|---|---|---|
| Capacity | **F2** for the mesh (dev and prod can share it, or dev can pause), or share the medallion platform's capacity | The mesh runs no Spark and no pipelines. Its compute is OneLake read transactions, the SQL endpoint and scanner calls. | F2 ≈ $263 / month always on; pausing it outside business hours halves that |
| Storage | OneLake | Shortcuts store nothing; storage is billed once, to the capacity that holds the source data | 485 MB ≈ cents per month, paid by the medallion platform |
| Shortcut reads | Consumer capacity | Read transactions through a shortcut are billed to the capacity of the workspace that holds the shortcut, not the source ([OneLake consumption](https://learn.microsoft.com/fabric/onelake/onelake-consumption)) | Small at this volume; moves cost from producer to consumer, which is the mesh's intent |
| Report viewers | Power BI Pro per viewer below F64 | On F2–F32 every viewer of a report needs a Pro license; from F64 Viewers are free | The break-even is roughly where Pro licenses cost more than the step to F64 |
| Sensitivity labels | Microsoft Purview Information Protection (Microsoft 365 E3/E5 or an Information Protection add-on) | Labels in Fabric need a Purview Information Protection license for users who apply or change them | Per user, typically already in an enterprise M365 agreement |

### Copy-based alternative

A copy-based mesh would store `fact_trips` (242 MB) twice more and run two more pipelines on a schedule. At this size
the storage is trivial; the real cost is the pipelines' compute and the people who keep them green. ADR 0001 records
the choice.

## 3. Governance

| Control | Declared in | Enforced by | Checked |
|---|---|---|---|
| Domain ownership (workspace → domain) | `fabric_domain_workspace_assignments` | Terraform | `workspace_domains.py`, daily |
| Domain contributors limited to the engineers group | `var.domains` → groups | `domain_contributors.py --apply` | dry run, daily |
| Default sensitivity label per domain | `var.domains.default_label` | Terraform (`fabric_domain`) | plan |
| Label per data product | `var.data_products.label` (default: the domain's) | `data_product_governance.py --apply` (user identity: `bulkSetLabels` rejects service principals) | dry run, daily |
| Tags | `var.data_products.tags` | Terraform (`fabric_lakehouse.tags`) | dry run, daily |
| Endorsement | `var.data_products.endorsement` | **Portal** (no write API) | scanner API, daily |
| Tenant settings | `tenant_settings.py` `DESIRED` | `--apply` | dry run, daily |
| Purview labels and label policy | `tools/purview/labels.ps1` | Security & Compliance PowerShell | not checked (no read API for the CI identity) |
| Lineage | implicit: shortcuts; `sourceWorkspace` in each contract | Fabric | `data-contracts` follows every shortcut chain, daily |
| Schema, row counts | `contracts/*.yml` (ODCS v3.1) | the medallion platform | `data-contracts`, daily (required) |
| Freshness | contract `latency` SLA (8 days) | the medallion platform's weekly schedule | `data-freshness`, daily (alert, not required) |

Drift handling is the same everywhere: the daily run fails, the fix is either a PR (change the code to match an intended
change) or `--apply` (restore the code's state).

## 4. Security

### Access model

Effective access to a table is the **intersection** of every hop's permission (shortcuts are passthrough).
Workspace Admins, Members and Contributors bypass OneLake roles **in their own workspace only**. Tables are restricted
on the source lakehouses; mesh lakehouses grant `*`, because Fabric rejects roles on shortcut paths. The README's
[Access model](../README.md#access-model) has the full role table and the live test with a license-free consumer.

### Identities

| Identity | Granted | Through |
|---|---|---|
| Human admin | Fabric Administrator, Global Administrator (trial only; removed when the trials end) | Entra roles |
| CI service principal `sp-fabric-mesh-governance` | Fabric admin APIs | member of `sg-fabric-automation` (tenant setting scope) |
| | Admin of each mesh workspace | member of each `sg-mesh-<domain>-owners` |
| | Member of `divvy-medallion-prod` (OneLake roles on the source need Member) | Terraform role assignment |
| | Graph `Group.ReadWrite.All`, `Directory.Read.All` | application permissions (tenant-wide: Graph has no per-group scope) |
| | HCP Terraform state | `TF_API_TOKEN`, the only repository secret |

No cloud secret exists: the CI identity signs in with GitHub OIDC federated credentials for `pull_request`, `main` and
the `platform` environment.

### Threat model for the CI identity

| Threat | Entry point | Impact | Mitigation | Residual risk |
|---|---|---|---|---|
| Malicious code in a PR runs during `plan` or `compliance` | PR from a branch of this repo | Acts as the CI identity before approval | Only write-access users can open such PRs; fork PRs get no credentials and are skipped (ADR 0004) | Accepted for one maintainer; a read-only plan identity is the fix |
| Unreviewed apply | Push to `main` | Tenant changes | `main` protected (PRs only, required checks, resolved threads); governance and prod applies wait for a reviewer on `platform`; dev applies without approval, but only to `mesh-*-dev` | A maintainer can approve their own change |
| Stolen OIDC token | Compromised runner | Short-lived token for this repo's subjects only | Federated credentials bound to repo + ref/environment; tokens live minutes | Window of minutes |
| Graph over-reach | `Group.ReadWrite.All` | Could modify any group in the tenant | Terraform manages only the 9 mesh groups; the CI identity owns them | Tenant-wide permission remains; use a dedicated tenant or administrative units in production |
| HCP token leak | Repository secret | Read/write of mesh state | Secret only in jobs that need it; state holds IDs, no credentials | Rotate on suspicion |
| Workspace Admin abuse | Owners group membership | Full control of a mesh workspace | Admin applies to the domain's own workspace only; upstream data still needs OneLake roles | — |
| Committed secrets | Developer mistake | Credential exposure | `.gitignore` for tfvars, plans and state; `local.auto.tfvars.example` with empty values; history scanned (ADR 0005) | — |
