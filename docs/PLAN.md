# Project plan

Fabric domain architecture (data mesh) + Purview governance, everything as code.
Upstream data comes from [fabric-medallion-cicd-terraform](https://github.com/felipecastro-data/fabric-medallion-cicd-terraform)
(`divvy-medallion-prod`) through OneLake shortcuts. No data is copied.

## Decisions

| Topic | Decision |
|---|---|
| Domains | **Mobility**, **Weather** (producers) → **Analytics** (consumer) |
| Data | Divvy trips + Open-Meteo weather from the medallion repo's prod gold/silver lakehouses |
| Licensing | Fabric trial capacity + **Microsoft 365 E5 Information Protection & Governance trial** (Purview Suite is an add-on that needs a base M365 license) |
| IaC | Terraform `microsoft/fabric` 1.14 + `hashicorp/azuread`, HCP Terraform remote state |
| Stacks | `governance` (tenant: groups, domains, domain roles, tags) and `domains` (workspaces, lakehouses, shortcuts, OneLake roles) |
| Not in Terraform | Applying labels to items (Admin REST `bulkSetLabels`), endorsement, applying tags to items → Python tools in `tools/` |

## Phases

- [x] **0. Plan**: scope, risks, provider coverage checked
- [x] **1. Scaffold**: repo layout, both Terraform stacks, `ci` (fmt · validate · tflint)
- [x] **2. Prerequisites**
  - [x] E5 Information Protection & Governance trial started (2026-11-03, 1 month), license assigned to the Fabric user
  - [x] Sensitivity labels + policy created as code: `tools/purview/labels.ps1`
  - [x] Tenant settings as code: `tools/tenant_settings.py` (domains, certification, master data applied)
  - [x] Label tenant settings: applied 2026-11-03 once the published labels reached Fabric (first attempt: 400 `UnknownError`)
  - [x] Fabric user can create Entra security groups (Global Administrator)
- [x] **3. Governance stack**: HCP workspace `fabric-mesh-governance` (local execution, state shared with `fabric-mesh-domains`);
  applied 2026-11-03: 9 groups, 3 domains, domain admins/contributors, 4 tags
  - [x] Domain default labels applied 2026-11-03: Mobility/Analytics = Confidential, Weather = Public
  - [x] Domain contributors restricted to the engineers group (`tools/domain_contributors.py`, preview Admin API; provider has no `contributors_scope`)
- [x] **4. Domains stack**: HCP workspace `fabric-mesh-domains`; applied 2026-11-03: 3 workspaces + lakehouses, group roles,
  domain assignment (provider preview), 12 shortcuts (7 to the medallion platform, 5 cross-domain).
  Verified: 6,006,901 trips readable in `lh_analytics` through two shortcut hops, zero copies; re-plan shows no drift
- [ ] **5. Access control**: OneLake security roles (consumers read dimensions/aggregates; ride-level `fact_trips` is engineers only)
  - [x] Role map in Terraform (`var.access_roles` → output `onelake_access_roles`), applied by `tools/onelake_roles.py` (2026-11-03: 6 roles)
  - [x] Table-level roles on the source lakehouses (`lh_gold`, `lh_silver`); mesh lakehouses grant `*` (Fabric rejects roles on shortcut paths)
  - [x] Live read test as `mesh-consumer-test` (member of `sg-mesh-analytics-consumers`, no Fabric license) through
    `lh_analytics` → producer → `lh_gold`: agg_daily_kpis 732, dim_station 2,028, dim_weather 365 rows; `fact_trips` denied
  - [ ] Move back to `fabric_onelake_data_access_security` when microsoft/terraform-provider-fabric#1044 ships
- [x] **6. Purview governance**
  - [x] Sensitivity labels on the data product lakehouses (and their SQL endpoints): `tools/data_product_governance.py` (`bulkSetLabels`)
  - [x] Endorsement: no write API in Fabric, so a documented portal step (2026-11-03: Mobility/Weather Certified, Analytics Promoted), verified by `tools/data_product_governance.py`
  - [x] Tags applied to the data product lakehouses (`applyTags`/`unapplyTags`), desired state in `var.data_products`
  - [x] Lineage across domains in the Fabric lineage view (divvy-prod `lh_gold` → `lh_mobility` → `lh_analytics`); the Purview hub is now OneLake catalog → Govern
  - [x] Screenshots in `docs/screenshots/` (lineage, endorsed data products, domains governance, OneLake security roles)
  - [ ] Optional: OneLake catalog tenant insights screenshot once its daily refresh picks up the domains
- [x] **7. CI/CD**: OIDC service principal, `terraform.yml` (plan comment on PR, approval-gated apply), governance compliance check
  - [x] Service principal `sp-fabric-mesh-governance` (GitHub OIDC; member of `sg-fabric-automation`; Graph
        `Group.ReadWrite.All` + `Directory.Read.All`; workspace Admin / source Member through Terraform)
  - [x] `terraform.yml`: plan comment per stack on PRs; governance → domains → tools apply behind `platform`
  - [x] `compliance.yml`: read-only drift check on PRs, `main` and daily (workspace domains, tenant settings,
        contributors, OneLake roles, labels / tags / endorsement)
  - [x] `main` protected: PRs only, `ci` + `compliance` required
- [ ] **8. Showcase**: README with diagrams, governance matrix, screenshots, impact
