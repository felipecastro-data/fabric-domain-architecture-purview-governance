# ADR 0008 — The Analytics data product is a Direct Lake semantic model

- **Status:** Accepted
- **Date:** 2026-11-05

## Context

Analytics is the consumer domain. Until now it only re-exposed producer tables through shortcuts: it showed access
paths across domains but built nothing of its own, so the repository had no transform and no serving endpoint. The
domain needs a product that combines Mobility and Weather (daily demand against weather), while keeping the rules
that make the mesh work: no copies, governed by the same labels and OneLake roles, defined as code.

## Options

| | Option | For | Against |
|---|---|---|---|
| A | **Derived Delta table** (notebook writes `daily_demand_weather` to a new lakehouse on a schedule) | A visible transform and stored output; any engine can read it | A copy and a pipeline to schedule and monitor, which is exactly what ADR 0001 avoided. It would also break "product lakehouses hold only shortcuts" unless it gets its own lakehouse. |
| B | **SQL view** on the `lh_analytics` SQL analytics endpoint | No copy | No Terraform or REST support for creating views; T-SQL over the endpoint from CI. OneLake security in the SQL endpoint needs user-identity mode. |
| C | **Import-mode semantic model** | Fast queries; works on any capacity | Copies the data into the model and needs scheduled refreshes |
| D | **Direct Lake semantic model** (TMDL, `fabric_semantic_model`) over `lh_analytics` | No copy: queries read the Delta files through the shortcut chain. Relationships and measures are the transform; the model is the endpoint for reports, Excel and DAX clients. Terraform manages it; OneLake security applies to every query (Direct Lake on OneLake uses the caller's identity). | Measures and relationships only, no new stored columns. Framing is needed after upstream writes (automatic updates, or a refresh call). Report viewers need Pro licences below F64. |

## Decision

**Option D.** `sm_demand_weather` in `mesh-analytics` (and `mesh-analytics-dev`), defined in TMDL under
[`semantic_models/demand_weather`](../../infra/terraform/domains/semantic_models/demand_weather) and deployed by
`fabric_semantic_model`. Its tables and types follow `contracts/analytics.yml`. It uses only consumer-readable tables
(`agg_daily_kpis`, `dim_date`, `dim_weather`), so every Analytics consumer can use every measure; ride-level
`fact_trips` stays out.

Measures: trips, trips per day, trips per dry and wet day, wet-day demand change, a weather baseline (trips per day for
the same temperature band and wet/dry flag across the calendar) and a **weather-adjusted demand index** (actual over
weather-expected demand), average duration and member share.

`semantic-model --refresh` frames the model after each apply, then runs a DAX query through the Power BI
`executeQueries` API and fails if any measure is blank. Compliance runs the query daily.

## Measured (dev, 2026-11-05)

| | |
|---|---|
| Framing | 18 s |
| DAX check (all measures) | 1.8 s |
| Trips · days | 1,597,858 · 62 |
| Trips per dry day · wet day | 28,025 · 23,208 |
| Wet-day demand change | −17.2 % |
| Member share | 61.2 % |

Deploying it surfaced two TMDL rules the provider doesn't check at plan time: descriptions are `///` comments, not a
`description:` property, and a measure can't share a name with any column (case-insensitive), so the hidden `trips`
column is `trip_count`.

## Consequences

- The consumer domain now has a transform and a serving endpoint with zero bytes copied.
- The model inherits the lakehouse's sensitivity label (downstream inheritance is enabled) and carries the
  `Data Product` and `Consumer Aligned` tags.
- A schema change upstream breaks the model's framing; the data contracts catch it first, in dev.
- **Revisit when:** the domain needs stored derived data (for example a daily snapshot other engines read). Then add a
  separate lakehouse with a scheduled notebook (Option A) and a contract for it.
