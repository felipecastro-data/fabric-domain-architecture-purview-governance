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
- [ ] **2. Prerequisites**
  - [x] E5 Information Protection & Governance trial started (2026-11-03, 1 month), license assigned to the Fabric user
  - [x] Sensitivity labels + policy created as code: `tools/purview/labels.ps1`
  - [x] Tenant settings as code: `tools/tenant_settings.py` (domains, certification, master data applied)
  - [ ] Label tenant settings: blocked until the published labels reach Fabric (up to 24 h), then re-run `--apply`
  - [x] Fabric user can create Entra security groups (Global Administrator)
- [x] **3. Governance stack**: HCP workspace `fabric-mesh-governance` (local execution, state shared with `fabric-mesh-domains`);
  applied 2026-11-03: 9 groups, 3 domains, domain admins/contributors, 4 tags
  - [ ] Domain default labels: re-apply once the label tenant settings are on
  - [ ] Domain contributors scope is still *entire tenant* (provider has no `contributors_scope`): restrict to the engineers group via Admin API
- [x] **4. Domains stack**: HCP workspace `fabric-mesh-domains`; applied 2026-11-03: 3 workspaces + lakehouses, group roles,
  domain assignment (provider preview), 12 shortcuts (7 to the medallion platform, 5 cross-domain).
  Verified: 6,006,901 trips readable in `lh_analytics` through two shortcut hops, zero copies; re-plan shows no drift
- [ ] **5. Access control**: OneLake data access roles (consumers read specific tables; ride-level data restricted)
- [ ] **6. Purview governance**
  - [ ] Sensitivity labels published; domain default labels; `tools/apply_labels.py`
  - [ ] Endorsement (promoted / certified): API or documented manual step
  - [ ] Tags applied to data product items
  - [ ] Lineage across domains in the Fabric lineage view + Purview hub / Unified Catalog
- [ ] **7. CI/CD**: OIDC service principal, `terraform.yml` (plan comment on PR, approval-gated apply), governance compliance check
- [ ] **8. Showcase**: README with diagrams, governance matrix, screenshots, impact
