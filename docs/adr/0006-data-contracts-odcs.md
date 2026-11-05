# ADR 0006 — Data contracts in ODCS v3.1, checked against the live tables

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

Data products are shortcuts (ADR 0001), so their schema is whatever the medallion platform writes. A renamed or
retyped column in `lh_gold` reaches every consumer at once, and nothing in this repository would notice. The mesh also
promises things it never wrote down: who owns a product, how fresh it is, what classification it carries, and that its
data really comes from `divvy-medallion-prod`.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **README tables** describing each product | Nothing to build | Not machine-checkable; drifts silently |
| B | **Custom YAML** read by a small checker | Exactly what we need | A private format nobody else can read or tool against |
| C | **ODCS v3.1** (Bitol, Linux Foundation) contracts, validated against the official JSON schema and checked live by a tool | Open standard with owners, roles, SLAs, quality rules and custom properties; other tools (data catalogs, `datacontract-cli`) can read the files | The standard has no OneLake server type, so the location comes from Terraform outputs; some checks (lineage) live in custom properties |
| D | **Purview data quality / Data Map** | Native to the governance stack | Needs Purview Unified Catalog and a paid data quality SKU beyond the E5 IP&G trial; not code |

## Decision

**Option C.** One contract per data product in [`contracts/`](../../contracts), scaffolded from the live tables with
`data-contracts --scaffold <domain>`, then curated (descriptions, keys, classification, owners, roles). The ODCS JSON
schema, vendored from [bitol-io/open-data-contract-standard](https://github.com/bitol-io/open-data-contract-standard)
(Apache-2.0) into `contracts/schema/`, is the single definition of a valid contract.

`data-contracts` (part of the required `compliance` check) reads each table **through the data product lakehouse**:

- **Schema:** a missing or retyped column is breaking and fails; a new column is reported as additive.
- **Row counts:** `rowCount` quality rules, from the Delta log statistics (no scan of 6M rows).
- **Lineage:** each table's OneLake shortcuts are followed hop by hop (`GET …/shortcuts`); the chain must end in the
  contract's `sourceWorkspace`. This is checked from the shortcut API rather than the scanner API, because the scanner
  does not report lakehouse-to-lakehouse shortcut lineage.

`data-freshness` checks the `latency` SLA (8 days: the weekly prod schedule plus a day) in a **separate, non-required
job**.

## Consequences

- A breaking change upstream fails the daily compliance run before a consumer reports it.
- Freshness alerts without blocking mesh PRs: the mesh cannot fix a paused or failing upstream pipeline. While the
  medallion prod schedule is paused (since 2026-11-04), the `data freshness` job will turn red after 8 days by design.
- Analytics re-exposes producer tables, so its contract repeats their schema. The check keeps the copies honest.
- **Revisit when:** a OneLake server type lands in ODCS, or Purview Unified Catalog data quality is licensed (then
  publish the contracts there and keep this check as the CI gate).
