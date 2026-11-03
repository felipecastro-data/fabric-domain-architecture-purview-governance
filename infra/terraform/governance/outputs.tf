output "domains" {
  description = "Domain key => { id, display_name, kind }. Consumed by the domains stack."
  value = {
    for k, d in fabric_domain.this : k => {
      id           = d.id
      display_name = d.display_name
      kind         = var.domains[k].kind
    }
  }
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
