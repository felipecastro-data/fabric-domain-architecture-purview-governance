# The Analytics domain's own data product: a Direct Lake semantic model over lh_analytics. It adds relationships and
# measures (the transform) and a query endpoint for reports and DAX clients (the serving layer), still without copying
# data: Direct Lake on OneLake reads the Delta files through the shortcut chain, with the caller's identity, so OneLake
# security applies to every query. It uses only consumer-readable tables (aggregates and dimensions, no fact_trips).
#
# The TMDL definition lives in semantic_models/demand_weather; its tables and types follow contracts/analytics.yml.

locals {
  semantic_model_path = "${path.module}/semantic_models/demand_weather"
}

resource "fabric_semantic_model" "demand_weather" {
  display_name = "sm_demand_weather"
  description  = "Analytics data product: daily demand against weather (Direct Lake on lh_analytics) — managed by Terraform"
  workspace_id = module.data_product["analytics"].workspace_id
  format       = "TMDL"
  tags         = [local.tags["Data Product"], local.tags["Consumer Aligned"]]

  definition = {
    for part in fileset(local.semantic_model_path, "**") : part => {
      source = "${local.semantic_model_path}/${part}"
      tokens = {
        WorkspaceId = module.data_product["analytics"].workspace_id
        LakehouseId = module.data_product["analytics"].lakehouse_id
      }
    }
  }

  # The model's tables are the cross-domain shortcuts; they must exist before the first framing
  depends_on = [fabric_shortcut.cross_domain]
}

output "semantic_models" {
  description = "Domain key => Direct Lake semantic model; semantic-model frames it and runs a DAX check."
  value = {
    analytics = {
      workspace_id = module.data_product["analytics"].workspace_id
      id           = fabric_semantic_model.demand_weather.id
      name         = fabric_semantic_model.demand_weather.display_name
    }
  }
}
