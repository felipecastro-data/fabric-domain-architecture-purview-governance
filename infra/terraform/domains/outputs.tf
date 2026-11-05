output "workspaces" {
  description = "Domain key => { workspace_id, lakehouse_id, domain_id }. src/fabric_mesh_tools/workspace_domains.py checks the domain assignments."
  value = {
    for k, m in module.data_product : k => {
      workspace_id = m.workspace_id
      lakehouse_id = m.lakehouse_id
      domain_id    = local.domains[k].id
    }
  }
}

output "workspace_prefix" {
  description = "Name prefix of every data product workspace."
  value       = "${var.project_name}-"
}

output "shortcuts" {
  description = "\"<domain>.<table>\" => shortcut source."
  value       = { for k, s in local.shortcuts : k => s.from }
}

output "data_product_governance" {
  description = "Domain key => lakehouse with its sensitivity label, tags (applied by Terraform) and endorsement — checked by src/fabric_mesh_tools/data_product_governance.py."
  value = {
    for k, p in var.data_products : k => {
      workspace_id = module.data_product[k].workspace_id
      item_id      = module.data_product[k].lakehouse_id
      item_type    = "Lakehouse"
      label        = coalesce(p.label, local.domains[k].default_label)
      label_id     = local.labels[coalesce(p.label, local.domains[k].default_label)]
      tags         = { for t in p.tags : t => data.terraform_remote_state.governance.outputs.tags[t] }
      endorsement  = local.is_prod ? p.endorsement : null # endorsement is a prod promise; dev items stay unendorsed
    }
  }
}
