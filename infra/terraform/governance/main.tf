# Central governance stack: owned by the Fabric administrators (tenant scope).
# Domain teams never change this stack; they consume its outputs in infra/terraform/domains.

locals {
  # One owners / engineers / consumers group per domain
  group_roles = {
    owners    = "Domain owners: domain admins and workspace Admins"
    engineers = "Domain engineers: domain contributors and workspace Contributors"
    consumers = "Data product consumers: workspace Viewers, table access through OneLake data access roles"
  }

  groups = merge([
    for d, domain in var.domains : {
      for r, description in local.group_roles : "${d}-${r}" => {
        domain      = d
        role        = r
        description = "${domain.display_name} — ${description} (managed by Terraform)"
      }
    }
  ]...)
}

data "azuread_client_config" "current" {}

resource "azuread_group" "this" {
  for_each = local.groups

  display_name     = "${var.group_prefix}-${each.key}"
  description      = each.value.description
  security_enabled = true
  owners           = distinct([data.azuread_client_config.current.object_id, var.admin_user_object_id, var.ci_service_principal_object_id])
  members          = each.value.role == "owners" ? [var.admin_user_object_id] : []

  # Membership of engineers / consumers groups is managed outside Terraform (access reviews, requests).
  lifecycle {
    ignore_changes = [members]
  }
}

resource "fabric_domain" "this" {
  for_each = var.domains

  display_name     = each.value.display_name
  description      = each.value.description
  default_label_id = lookup(var.sensitivity_label_ids, each.value.default_label, null)
}

resource "fabric_domain_role_assignments" "admins" {
  for_each = var.domains

  domain_id = fabric_domain.this[each.key].id
  role      = "Admins"

  principals = [{
    id   = azuread_group.this["${each.key}-owners"].object_id
    type = "Group"
  }]
}

resource "fabric_domain_role_assignments" "contributors" {
  for_each = var.domains

  domain_id = fabric_domain.this[each.key].id
  role      = "Contributors"

  principals = [{
    id   = azuread_group.this["${each.key}-engineers"].object_id
    type = "Group"
  }]
}

resource "fabric_tag" "this" {
  for_each = var.tags

  display_name = each.value

  scope = {
    type = "Tenant"
  }
}
