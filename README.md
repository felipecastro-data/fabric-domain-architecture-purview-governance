# Fabric Data Mesh — Domains · OneLake Shortcuts · Purview Governance (Terraform)

[![ci](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/ci.yml/badge.svg)](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/ci.yml)
[![terraform](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/terraform.yml/badge.svg)](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/terraform.yml)
[![compliance](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/compliance.yml/badge.svg)](https://github.com/felipecastro-data/fabric-domain-architecture-purview-governance/actions/workflows/compliance.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A **data-mesh architecture on Microsoft Fabric**, governed end to end and **defined as code**. Fabric **domains** own
their workspaces. Producer domains publish **data products** through **OneLake shortcuts**, with zero copies. A
consumer domain combines them across domains. **OneLake data access roles**, **Microsoft Purview sensitivity labels**,
**endorsement**, **tags** and **lineage** decide who reads what and which data can be trusted. A daily **compliance check** proves the live tenant still matches the code.

The data products expose real Chicago **Divvy** bike-share trips and **Open-Meteo** weather. The sibling project
[fabric-medallion-cicd-terraform](https://github.com/felipecastro-data/fabric-medallion-cicd-terraform) produces that
data. This repository adds the mesh and the governance on top, without moving a single row.

| At a glance | |
|---|---|
| Domains | **3 Fabric domains**: Mobility and Weather (producers), Analytics (consumer). Each has an owners, engineers and consumers Entra group. |
| Data products | **12 OneLake shortcuts**, **0 copies**. `fact_trips` (**6.0M rows**) is read through 2 shortcut hops from the prod medallion lakehouse. |
| Access | **6 OneLake security roles**. Consumers read dimensions and aggregates only; ride-level data is for engineers. Verified live as a consumer test user. |
| Governance | Sensitivity labels, tags, endorsement and domain contributor scope for every data product, all declared in Terraform. |
| As code | **56 Terraform resources** in 2 stacks, plus **5 idempotent Python tools** for what the provider can't manage. |
| Delivery | GitHub OIDC (no secrets), a plan comment per stack on every PR, an approval-gated apply, and a required **compliance** check that also runs daily. |

## Architecture

```mermaid
flowchart LR
    subgraph SRC["divvy-medallion-prod · medallion platform (sibling repo)"]
        G[("lh_gold<br/>fact_trips · dim_station · dim_date<br/>dim_weather · agg_*")]
        S[("lh_silver<br/>weather_daily")]
    end
    subgraph DM["Domain: Mobility · producer"]
        M[("lh_mobility<br/>Confidential · Certified")]
    end
    subgraph DW["Domain: Weather · producer"]
        W[("lh_weather<br/>Public · Certified")]
    end
    subgraph DA["Domain: Analytics · consumer"]
        A[("lh_analytics<br/>Confidential · Promoted")]
    end
    G -- "5 shortcuts" --> M
    G -- "dim_weather" --> W
    S -- "weather_daily" --> W
    M -- "4 cross-domain shortcuts" --> A
    W -- "dim_weather" --> A
    PV{{"Microsoft Purview<br/>labels · endorsement · tags · lineage"}} -. governs .-> DM & DW & DA
```

Every data product lakehouse holds **only shortcuts**. The data stays in the medallion platform's prod workspace, and
the mesh adds ownership, discoverability and access control on top of it.

### Ownership: two Terraform stacks

```mermaid
flowchart LR
    subgraph GOV["infra/terraform/governance · central governance (tenant scope)"]
        GR["9 Entra groups<br/>owners · engineers · consumers"]
        DO["3 domains + default labels"]
        DR["Domain admins / contributors"]
        TG["4 tenant tags"]
    end
    subgraph DOM["infra/terraform/domains · domain platform teams"]
        WS["Workspaces + data product lakehouses"]
        SC["12 shortcuts"]
        RA["Workspace roles · domain assignment · tags"]
        OR["OneLake role map"]
    end
    HCP[("HCP Terraform<br/>remote state")]
    GOV -- outputs --> HCP -- terraform_remote_state --> DOM
    DOM -- "terraform output" --> T["tools/*.py<br/>roles · labels · endorsement check"]
```

The central stack is applied first. Domain teams consume its outputs (domain IDs, group IDs, label IDs, tag IDs) and
never touch tenant-scope resources.

## Governance matrix

| Domain | Kind | Data product | Sensitivity label | Tags | Endorsement | OneLake roles |
|---|---|---|---|---|---|---|
| Mobility | producer | `lh_mobility` | **Confidential** | Data Product · Source Aligned · Contains Ride Data | ✅ **Certified** | `CrossDomainRead` (Analytics) |
| Weather | producer | `lh_weather` | **Public** | Data Product · Source Aligned | ✅ **Certified** | `CrossDomainRead` (Analytics) |
| Analytics | consumer | `lh_analytics` | **Confidential** | Consumer Aligned · Contains Ride Data | ⭐ **Promoted** | Built-in `DefaultReader` |

Each domain has a **default sensitivity label**, so new items are labelled on creation. Domain contributors are
restricted to the domain's engineers group (`SpecificUsersAndGroups`, not the default "entire tenant").

## Access model

| Group (per domain) | Domain role | Workspace role | Data access |
|---|---|---|---|
| `sg-mesh-<domain>-owners` | Admin | Admin | Everything in the domain's workspace |
| `sg-mesh-<domain>-engineers` | Contributor | Contributor | Everything in the domain's workspace; Mobility and Analytics engineers also read ride-level data upstream |
| `sg-mesh-<domain>-consumers` | — | Viewer | Only the tables a OneLake security role grants |

OneLake shortcuts are **passthrough**: a reader needs a role **at every hop**, and effective access is the
**intersection**. Fabric rejects roles on shortcut paths, so the mesh lakehouses grant `*` to cross-domain readers,
and table-level restrictions live on the source lakehouses where the data is. A Terraform validation enforces
that rule.

```mermaid
flowchart LR
    U(["analytics-consumer"]) --> A["lh_analytics<br/>workspace Viewer"]
    A --> M["lh_mobility<br/>CrossDomainRead: *"]
    M --> G["lh_gold<br/>MeshAggregates:<br/>dim_station · dim_date · agg_*"]
    G --> OK["✅ aggregates and dimensions"]
    G -. "fact_trips is not in the role" .-> NO["⛔ ride-level data denied"]
```

| Role | Lakehouse | Tables | Granted to |
|---|---|---|---|
| `CrossDomainRead` | `lh_mobility` | `*` (passthrough) | analytics consumers, analytics engineers |
| `CrossDomainRead` | `lh_weather` | `*` (passthrough) | analytics consumers, analytics engineers |
| `MeshAggregates` | divvy-prod `lh_gold` | dim_station, dim_date, agg_daily_kpis, agg_station_monthly | mobility consumers, analytics consumers |
| `MeshRideLevel` | divvy-prod `lh_gold` | **fact_trips** + the 4 above | mobility engineers, analytics engineers |
| `MeshWeather` | divvy-prod `lh_gold` | dim_weather | weather and analytics, consumers and engineers |
| `MeshWeather` | divvy-prod `lh_silver` | weather_daily | weather consumers, weather engineers |

### Verified as a real consumer

A test user whose only access is membership of `sg-mesh-analytics-consumers` (no Fabric license) read the
Analytics lakehouse over OneLake. Each read went through `lh_analytics` → producer lakehouse → `lh_gold`:

| Table | Path | Result |
|---|---|---|
| `agg_daily_kpis` | 2 hops | ✅ 732 rows |
| `dim_station` | 2 hops | ✅ 2,028 rows |
| `dim_weather` | 2 hops | ✅ 365 rows |
| `fact_trips` | 2 hops | ⛔ denied ("lacked the necessary privileges") |

Analytics engineers hold a role at every hop and read all 6,006,901 rows of `fact_trips`. Membership of an owners
group alone does not: workspace Admin applies only in the domain's own workspace, not at upstream hops.
[`tools/read_onelake.py`](tools/read_onelake.py) reproduces the test.

## Delivery

```mermaid
flowchart LR
    PR["Pull request"] -->|"ci: fmt · validate · tflint<br/>terraform: plan comment per stack<br/>compliance: live state vs deployed policy"| Main["main (protected)"]
    Main -->|"approval: platform"| Apply["apply governance → domains<br/>then tools: tenant settings · contributors<br/>OneLake roles · tags · label/endorsement check"]
    Apply --> C["compliance<br/>after every apply + daily 06:00 UTC"]
```

- **No secrets**: the CI service principal signs in with GitHub OIDC federated credentials. The HCP Terraform token
  is the only repository secret.
- **A dedicated CI identity**: one service principal for this repo. It gets Fabric admin APIs through a single
  automation group and is Admin of only the mesh workspaces. It is Member of the source workspace, which OneLake
  security management requires. Graph access covers the mesh groups.
- **`main` is protected**: changes land through PRs only, `ci` and `compliance` are required, and review threads must be resolved.
- **Compliance** fails the build when any of these drifts from Terraform: a workspace's domain, a tenant setting, a
  domain's contributor scope, a OneLake role, a label, a tag set or an endorsement.

## What is code, and what isn't

| Concern | Managed by | How |
|---|---|---|
| Groups, domains, domain roles, default labels, tags | Terraform `governance` | `azuread_group`, `fabric_domain`, `fabric_domain_role_assignments`, `fabric_tag` |
| Workspaces, lakehouses, workspace roles, domain assignment, shortcuts, item tags | Terraform `domains` | `fabric_workspace`, `fabric_lakehouse`, `fabric_domain_workspace_assignments`, `fabric_shortcut` |
| OneLake security roles | Terraform role map → [`onelake_roles.py`](tools/onelake_roles.py) | Single-role upsert. The provider resource fails on Entra members ([#1044](https://github.com/microsoft/terraform-provider-fabric/issues/1044)). |
| Sensitivity labels on existing items | Terraform → [`data_product_governance.py`](tools/data_product_governance.py) | `bulkSetLabels` (user-only API, so CI only checks labels) |
| Domain contributor scope | [`domain_contributors.py`](tools/domain_contributors.py) | Admin API (`contributorsScope` is preview-only) |
| Tenant settings (labels, endorsement, domains) | [`tenant_settings.py`](tools/tenant_settings.py) | Admin API |
| Purview labels and label policy | [`purview/labels.ps1`](tools/purview/labels.ps1) | Security & Compliance PowerShell |
| **Endorsement** | **Portal** (no write API exists) | Set once in item settings. Terraform declares it, and the compliance check fails while it differs. |

The Python tools are idempotent. Each runs as a dry run by default, exits 1 on drift, and makes changes only with
`--apply`. All of them except `tenant_settings.py` read their desired state from `terraform output`, so there is one
source of truth; `tenant_settings.py` keeps its own `DESIRED` map. `labels.ps1` is idempotent too, but it has no dry
run: it creates or updates the labels and publishes the label policy as soon as it runs.

## What the gates caught

Each of these was found by a plan, a failed apply, a live test or a review, before it could become silent drift.

| Found by | Problem | Fix |
|---|---|---|
| Terraform apply | `fabric_onelake_data_access_security` fails with "inconsistent result after apply" for Entra members; the API never returns `objectType` | Role map stays in Terraform, applied by a Python upsert tool until the provider fix ships |
| Fabric API | Table-level roles on shortcut paths are rejected (`defining roles for SSO shortcuts is not supported`) | Restrictions moved to the source lakehouses; Terraform validation blocks the pattern |
| API review | `PUT …/dataAccessRoles` replaces **all** roles on an item, including ones this repo doesn't own | Tool upserts one role at a time with `POST` and lists unmanaged roles instead of deleting them |
| Scanner check | A domain default label only applies to items created afterwards, so the existing lakehouses had no label | `bulkSetLabels` from the Terraform-declared label; SQL endpoints inherit it |
| Domain review | New domains let the **entire tenant** contribute workspaces | Contributor scope restricted to the engineers group; checked on every run |
| CI bootstrap plan | A provider update started tracking lakehouse `tags` and planned to strip the tags the tool had applied | Tags moved into Terraform; the tool now only checks them |
| Live consumer test | The Fabric REST API returns 401 `UserNotLicensed` for a license-free consumer, but OneLake reads work | Reader takes lakehouse GUIDs, so consumers are tested exactly as they read |
| Code review | A required compliance check would block policy-changing PRs and every fork PR | PRs check live state against the deployed policy (base-branch tools); fork PRs skip safely |

## Screenshots

### Lineage: data products without copies

| Mobility reads the medallion platform's prod lakehouse | Analytics combines both producer domains |
|---|---|
| ![Lineage: lh_mobility from divvy-medallion-prod](docs/screenshots/lineage-mobility-from-divvy-prod.jpg) | ![Lineage: lh_analytics from lh_mobility and lh_weather](docs/screenshots/lineage-analytics-cross-domain.jpg) |

### Trust: labels and endorsement

| Mobility data product: Certified and Confidential | OneLake catalog: endorsed data products by domain |
|---|---|
| ![mesh-mobility workspace with a Certified, Confidential lakehouse](docs/screenshots/workspace-mobility-certified-confidential.jpg) | ![OneLake catalog with endorsed data products](docs/screenshots/onelake-catalog-endorsed-data-products.jpg) |

### Governance and security

| Domains: contributor scope and default labels | OneLake security roles across the mesh and the source |
|---|---|
| ![OneLake catalog Govern: 3 domains, SpecificUsersAndGroups, default labels](docs/screenshots/govern-domains-scope-and-labels.jpg) | ![OneLake catalog Secure: roles on lh_gold, lh_silver and the mesh lakehouses](docs/screenshots/onelake-security-roles.jpg) |

### Delivery

| Terraform plan posted per stack on every pull request | Apply gated by a manual approval on `platform` |
|---|---|
| ![Terraform plan PR comments for the governance and domains stacks](docs/screenshots/ci-terraform-plan-pr-comments.jpg) | ![terraform apply run approved on the platform environment](docs/screenshots/ci-apply-approval-gate.jpg) |

### Manual step: endorsement

Fabric has **no API** to promote or certify an item. Endorsement is set once in the portal: **workspace → item `…`
→ Settings → Endorsement**. Terraform still declares it (`endorsement = "Certified"`), and
`data_product_governance.py` reads it back through the scanner API. Until the portal matches, the compliance check
fails. The Mobility screenshot above shows the result.

## Tech stack

| Area | Tools |
|---|---|
| Platform | Microsoft Fabric: Domains, Lakehouse, OneLake shortcuts, OneLake security, OneLake catalog |
| Governance | Microsoft Purview Information Protection (sensitivity labels), Fabric endorsement, tags, lineage, scanner API |
| Identity | Microsoft Entra ID groups, service principal with GitHub OIDC federated credentials |
| Infrastructure as code | Terraform `microsoft/fabric` + `hashicorp/azuread`, HCP Terraform remote state, tflint |
| Automation | Python 3 (standard library only) on the Fabric REST and Admin APIs, PowerShell for Purview labels |
| CI/CD | GitHub Actions, environments with required reviewers, protected `main`, scheduled compliance |

## Repository layout

```
infra/terraform/governance/   tenant scope: Entra groups · domains · domain roles · default labels · tags
infra/terraform/domains/      workspaces · data product lakehouses · roles · shortcuts · OneLake role map · governance outputs
tools/                        idempotent tools for what the provider can't manage (+ OneLake reader for access tests)
tools/purview/                Purview sensitivity labels and label policy (PowerShell)
docs/                         plan, screenshots
.github/workflows/            ci (fmt · validate · tflint) · terraform (plan / apply) · compliance (drift check)
```

## Run it yourself

You need a Fabric capacity (a trial works), Microsoft Purview Information Protection (an E5 trial works), an HCP
Terraform organization, and the medallion platform from the
[sibling repo](https://github.com/felipecastro-data/fabric-medallion-cicd-terraform) as the data source.

1. Point Terraform at your HCP organization. Replace `felipecastro-data` in both stacks' `versions.tf` `cloud`
   blocks and in the `terraform_remote_state` block of `infra/terraform/domains/main.tf`. Then create the workspaces
   `fabric-mesh-governance` and `fabric-mesh-domains`, both with execution mode **Local**.
2. Create the CI identity: an Entra app and service principal with GitHub OIDC federated credentials (pull requests,
   `main` and the `platform` environment). Its object ID is a Terraform input from the first apply on.
3. Create the labels and label policy: `pwsh tools/purview/labels.ps1 -UserPrincipalName <admin upn>`. This applies
   them immediately and writes the label IDs to `labels.auto.tfvars.json`.
4. Enable the tenant settings: `python tools/tenant_settings.py --apply`.
5. Write each stack's `local.auto.tfvars` (it is gitignored):
   - `governance`: `admin_user_object_id` and `ci_service_principal_object_id`;
   - `domains`: `capacity_id`.
6. Apply `infra/terraform/governance`, then `infra/terraform/domains`.
7. Apply the rest: `onelake_roles.py --apply`, `domain_contributors.py --apply` and
   `data_product_governance.py --apply`. Set endorsement in the portal.
8. For CI:
   - set the repository variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `FABRIC_CAPACITY_ID`,
     `FABRIC_ADMIN_USER_OBJECT_ID`, `FABRIC_SP_OBJECT_ID` and `SENSITIVITY_LABEL_IDS`, and the `TF_API_TOKEN` secret;
   - create the `platform` environment and add **required reviewers** to it. Without that protection rule, applies
     run without waiting for approval.

Progress and decisions are in [docs/PLAN.md](docs/PLAN.md). Working conventions are in [CLAUDE.md](CLAUDE.md).

## 🏅 Author & Certifications

**Felipe Castro**
Senior Data Engineer @ EPAM Systems

- 🏅 **[DP-700: Microsoft Certified: Fabric Data Engineer Associate](https://learn.microsoft.com/api/credentials/share/en-us/FelipeCastro-8026/96572499DF943EBC?sharingId=13D660F56C1DFFA3)**
- 🏅 **[DP-600: Microsoft Certified: Fabric Analytics Engineer Associate](https://learn.microsoft.com/api/credentials/share/en-us/FelipeCastro-8026/6C5A2F5A8A5864FC?sharingId=13D660F56C1DFFA3)**
- 🏅 **[PL-300: Microsoft Certified: Power BI Data Analyst Associate](https://learn.microsoft.com/api/credentials/share/en-us/FelipeCastro-8026/F853AABE365874B3?sharingId=13D660F56C1DFFA3)**

---

## 🚀 Tools & Tech

![Microsoft Fabric](https://img.shields.io/badge/Microsoft%20Fabric-000000?style=flat&logo=Microsoft&logoColor=white)
![Microsoft Purview](https://img.shields.io/badge/Microsoft%20Purview-0078D4?style=flat&logo=microsoft&logoColor=white)
![Terraform](https://img.shields.io/badge/Terraform-844FBA?style=flat&logo=terraform&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=flat&logo=githubactions&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white)
![PowerShell](https://img.shields.io/badge/PowerShell-5391FE?style=flat&logo=powershell&logoColor=white)
![Azure](https://img.shields.io/badge/Microsoft_Azure-0078D4?style=flat&logo=microsoftazure&logoColor=white)
![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat&logo=github&logoColor=white)

---

## License

[MIT](LICENSE)
