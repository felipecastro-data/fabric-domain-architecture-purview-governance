output "workspace_id" {
  description = "ID of the workspace."
  value       = fabric_workspace.this.id
}

output "lakehouse_id" {
  description = "ID of the data product lakehouse."
  value       = fabric_lakehouse.this.id
}
