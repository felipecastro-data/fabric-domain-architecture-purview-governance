# Environments: the same domains, data products and roles in dev and prod, each with its own HCP workspace (state).
# Tenant-scope resources (groups, domains, tags) are shared: they live in the governance stack, applied once.
#
#   environment | HCP workspace            | workspaces            | source (medallion platform) | endorsement
#   dev         | fabric-mesh-domains-dev  | mesh-<domain>-dev     | divvy-medallion-dev         | not checked
#   prod        | fabric-mesh-domains      | mesh-<domain>         | divvy-medallion-prod        | Terraform-declared
#
# Prod keeps its original names, so introducing environments changed nothing in prod.

variable "environment" {
  description = "Deployment environment: dev or prod. CI sets TF_VAR_environment together with TF_WORKSPACE."
  type        = string

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "environment must be dev or prod."
  }
}

variable "source_workspace_names" {
  description = "Upstream medallion workspace per environment, whose Delta tables the producer domains expose."
  type        = map(string)
  default = {
    dev  = "divvy-medallion-dev"
    prod = "divvy-medallion-prod"
  }
}

locals {
  is_prod               = var.environment == "prod"
  name_suffix           = local.is_prod ? "" : "-${var.environment}"
  source_workspace_name = var.source_workspace_names[var.environment]
}

output "environment" {
  description = "Environment of this state."
  value       = var.environment
}

output "source_workspace_name" {
  description = "Upstream workspace every data product's shortcut chain must end in (checked by data-contracts)."
  value       = local.source_workspace_name
}

output "workspace_name_pattern" {
  description = "Regex for this environment's data product workspace names; workspace-domains flags unmanaged matches."
  value       = local.is_prod ? "^${var.project_name}-[a-z0-9]+$" : "^${var.project_name}-[a-z0-9]+${local.name_suffix}$"
}
