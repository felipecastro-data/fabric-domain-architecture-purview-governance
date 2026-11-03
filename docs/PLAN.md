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
  - [ ] Confirm the Fabric user can create Entra security groups (or create them once as an admin)
- [ ] **3. Governance stack**: HCP workspace `fabric-mesh-governance`, apply groups + domains + domain roles + tags
- [ ] **4. Domains stack**: HCP workspace `fabric-mesh-domains`, apply workspaces + lakehouses + domain assignment + shortcuts
- [ ] **5. Access control**: OneLake data access roles (consumers read specific tables; ride-level data restricted)
- [ ] **6. Purview governance**
  - [ ] Sensitivity labels published; domain default labels; `tools/apply_labels.py`
  - [ ] Endorsement (promoted / certified): API or documented manual step
  - [ ] Tags applied to data product items
  - [ ] Lineage across domains in the Fabric lineage view + Purview hub / Unified Catalog
- [ ] **7. CI/CD**: OIDC service principal, `terraform.yml` (plan comment on PR, approval-gated apply), governance compliance check
- [ ] **8. Showcase**: README with diagrams, governance matrix, screenshots, impact
