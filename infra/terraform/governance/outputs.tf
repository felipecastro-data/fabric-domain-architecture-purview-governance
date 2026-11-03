output "domains" {
  description = "Domain key => { id, display_name, kind, default_label }. Consumed by the domains stack."
  value = {
    for k, d in fabric_domain.this : k => {
      id            = d.id
      display_name  = d.display_name
      kind          = var.domains[k].kind
      default_label = var.domains[k].default_label
    }
  }
}

output "labels" {
  description = "Purview sensitivity label display name => label ID."
  value       = var.sensitivity_label_ids
}

output "groups" {
  description = "\"<domain>-<role>\" => Entra group object ID."
  value       = { for k, g in azuread_group.this : k => g.object_id }
}

output "tags" {
  description = "Tag display name => tag ID."
  value       = { for k, t in fabric_tag.this : k => t.id }
}

output "tenant_id" {
  description = "Entra tenant ID, used for OneLake security role members."
  value       = data.azuread_client_config.current.tenant_id
}

output "ci_service_principal_object_id" {
  description = "Entra object ID of the CI service principal. The domains stack makes it workspace Admin."
  value       = var.ci_service_principal_object_id
}
