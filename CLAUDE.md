# Working on this repository

Microsoft Fabric data mesh (domains, workspaces, OneLake shortcuts) governed with Purview (sensitivity labels,
endorsement, lineage) and OneLake data access roles, all as code. Progress and checklists: [docs/PLAN.md](docs/PLAN.md).
Sibling repo (data source, same conventions): `../fabric-cidc-iac-medallion-project`.

## Start of every session — verify, don't ask

```bash
eval "$(/opt/homebrew/bin/brew shellenv zsh)"
az account show --query user.name -o tsv          # new_user_fabric@felipe9393icloud384.onmicrosoft.com (Fabric Administrator)
gh auth status                                     # felipecastro-data
ls ~/.terraform.d/credentials.tfrc.json            # HCP Terraform (org felipecastro-data)
az rest --method get --resource https://api.fabric.microsoft.com \
  --url https://api.fabric.microsoft.com/v1/admin/domains -o json
```

## Rules

- Two Terraform stacks, applied in order: `infra/terraform/governance` (tenant scope) → `infra/terraform/domains`
  (reads governance outputs from HCP remote state). Never put tenant-scope resources in `domains`.
- Data product lakehouses hold **only shortcuts**; source data stays in `divvy-medallion-prod`.
- Anything the provider cannot manage goes into an idempotent Python tool in `tools/`, never a manual portal step
  (unless no API exists; then document it in the README with a screenshot).
- Local variable values live in `local.auto.tfvars` (gitignored); CI uses `TF_VAR_*` from GitHub variables.
