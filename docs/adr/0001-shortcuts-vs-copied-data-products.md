# ADR 0001 — Data products as OneLake shortcuts instead of copied tables

- **Status:** Accepted
- **Date:** 2026-11-03

## Context

The mesh has two producer domains (Mobility, Weather) and one consumer domain (Analytics). The data already exists:
the sibling medallion platform writes Divvy trips and Open-Meteo weather to `lh_gold` and `lh_silver` in
`divvy-medallion-prod`, refreshed weekly. Each domain must own a data product it can label, endorse, tag and secure,
and the consumer must combine products from two domains.

The forces:

- **Freshness.** A consumer should see what prod has, without a second schedule to monitor.
- **Storage and pipelines.** `fact_trips` is 6.0M rows and 242 MB. Every copy adds storage, a pipeline and a failure mode.
- **Security across hops.** Restrictions must hold whatever path a reader takes to a table.
- **Ownership.** Producers must not depend on the medallion team to publish, and the medallion repo must not know
  about the mesh.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **Copy** each product table into the domain lakehouse (pipeline or notebook per domain) | Each domain fully owns its bytes. Security is local to one lakehouse. Producers can reshape data. | One more copy per domain that exposes a table (`fact_trips` twice more). A pipeline per hop to build, schedule and monitor. Data is as stale as the slowest copy. Lineage stops at the copy. |
| B | **Share the source lakehouse** directly (workspace or item permissions on `divvy-medallion-prod`) | Zero copies, nothing to build | No domain boundary: there is nothing for a domain to own, label or endorse. Consumers couple to the medallion workspace layout. |
| C | **OneLake shortcuts**: each domain lakehouse holds shortcuts to the source; the consumer holds shortcuts to the producers | Zero copies and always as fresh as prod. Each domain owns an item it can govern. Fabric lineage follows the chain to the source. | Access is the intersection of every hop (passthrough). Fabric rejects OneLake roles on shortcut paths, so table-level rules must live on the source. Producers cannot reshape data without a transform of their own. |

## Decision

**Option C.** Data product lakehouses hold **only shortcuts** (a rule in [CLAUDE.md](../../CLAUDE.md)), declared in
`var.data_products` and created by `fabric_shortcut`. Table-level OneLake roles live on the source lakehouses, and the
mesh lakehouses grant `*` to cross-domain readers; a Terraform validation blocks roles on shortcut paths.

## Consequences

- 0 bytes copied: 12 shortcuts serve 485 MB in place. No pipeline exists in this repository.
- Every read pays one OneLake read transaction per hop, billed to the capacity of the workspace that holds the shortcut
  (see [design.md](../design.md#2-cost)).
- A reader needs a role at every hop. Owners of a domain are Admins of their own workspace only, so they are denied
  upstream tables unless a role grants them, which is intended (see the access chart in the README).
- The product schema is the source schema. Data contracts pin it (ADR 0006), so a breaking change in the medallion
  repo fails the compliance check instead of reaching consumers silently.
- **Revisit when:** a producer needs a different shape than the source (then add a transform that writes to a separate
  lakehouse, keeping the shortcut-only rule for the product lakehouse), or a shortcut chain approaches the OneLake limit
  of 10 shortcuts per path.
