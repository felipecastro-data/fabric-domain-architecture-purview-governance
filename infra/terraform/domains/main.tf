# Domain stack: one workspace + data product lakehouse per domain, assigned to its Fabric domain,
# exposed through OneLake shortcuts (no data is copied).

data "terraform_remote_state" "governance" {
  backend = "remote"

  config = {
    organization = "felipecastro-data"
    workspaces = {
      name = "fabric-mesh-governance"
    }
  }
}

locals {
  domains = data.terraform_remote_state.governance.outputs.domains
  groups  = data.terraform_remote_state.governance.outputs.groups
  labels  = data.terraform_remote_state.governance.outputs.labels
  tags    = data.terraform_remote_state.governance.outputs.tags
  ci_sp   = data.terraform_remote_state.governance.outputs.ci_service_principal_object_id

  source_lakehouses = toset(distinct([
    for s in flatten([for p in values(var.data_products) : values(p.shortcuts)]) :
    trimprefix(s.from, "source:") if startswith(s.from, "source:")
  ]))
}

# Upstream medallion platform (github.com/felipecastro-data/fabric-medallion-cicd-terraform)
data "fabric_workspace" "source" {
  display_name = var.source_workspace_name
}

# The CI service principal manages the OneLake roles on the source lakehouses (tools/onelake_roles.py),
# which needs Member on the source workspace.
resource "fabric_workspace_role_assignment" "source_ci" {
  workspace_id = data.fabric_workspace.source.id
  role         = "Member"

  principal = {
    id   = local.ci_sp
    type = "ServicePrincipal"
  }
}

data "fabric_lakehouse" "source" {
  for_each = local.source_lakehouses

  workspace_id = data.fabric_workspace.source.id
  display_name = each.key
}

module "data_product" {
  source   = "./modules/data_product_workspace"
  for_each = var.data_products

  display_name            = "${var.project_name}-${each.key}"
  description             = "${local.domains[each.key].display_name} domain workspace (${local.domains[each.key].kind}) — managed by Terraform"
  capacity_id             = var.capacity_id
  lakehouse_name          = each.value.lakehouse
  lakehouse_description   = each.value.description
  lakehouse_tag_ids       = [for t in each.value.tags : local.tags[t]]
  ci_service_principal_id = local.ci_sp

  group_ids = {
    owners    = local.groups["${each.key}-owners"]
    engineers = local.groups["${each.key}-engineers"]
    consumers = local.groups["${each.key}-consumers"]
  }
}

resource "fabric_domain_workspace_assignments" "this" {
  for_each = var.data_products

  domain_id     = local.domains[each.key].id
  workspace_ids = [module.data_product[each.key].workspace_id]
}

locals {
  # Every shortcut target, keyed by the `from` value used in var.data_products
  shortcut_sources = merge(
    { for lh, d in data.fabric_lakehouse.source : "source:${lh}" => { workspace_id = d.workspace_id, item_id = d.id } },
    { for k, m in module.data_product : k => { workspace_id = m.workspace_id, item_id = m.lakehouse_id } },
  )

  shortcuts = merge([
    for product, p in var.data_products : {
      for name, s in p.shortcuts : "${product}.${name}" => {
        product = product
        name    = name
        from    = s.from
        table   = s.table
      }
    }
  ]...)

  source_shortcuts       = { for k, s in local.shortcuts : k => s if startswith(s.from, "source:") }
  cross_domain_shortcuts = { for k, s in local.shortcuts : k => s if !startswith(s.from, "source:") }
}

# Producer domains: shortcuts into the upstream medallion platform
resource "fabric_shortcut" "source" {
  for_each = local.source_shortcuts

  workspace_id = module.data_product[each.value.product].workspace_id
  item_id      = module.data_product[each.value.product].lakehouse_id
  path         = "Tables/dbo"
  name         = each.value.name

  target = {
    onelake = {
      workspace_id = local.shortcut_sources[each.value.from].workspace_id
      item_id      = local.shortcut_sources[each.value.from].item_id
      path         = "Tables/dbo/${each.value.table}"
    }
  }
}

# Consumer domains: shortcuts to producer data products (which are shortcuts themselves), so they must exist first
resource "fabric_shortcut" "cross_domain" {
  for_each = local.cross_domain_shortcuts

  depends_on = [fabric_shortcut.source]

  workspace_id = module.data_product[each.value.product].workspace_id
  item_id      = module.data_product[each.value.product].lakehouse_id
  path         = "Tables/dbo"
  name         = each.value.name

  target = {
    onelake = {
      workspace_id = local.shortcut_sources[each.value.from].workspace_id
      item_id      = local.shortcut_sources[each.value.from].item_id
      path         = "Tables/dbo/${each.value.table}"
    }
  }
}
