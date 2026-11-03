output "workspaces" {
  description = "Domain key => { workspace_id, lakehouse_id }."
  value = {
    for k, m in module.data_product : k => {
      workspace_id = m.workspace_id
      lakehouse_id = m.lakehouse_id
    }
  }
}

output "shortcuts" {
  description = "\"<domain>.<table>\" => shortcut source."
  value       = { for k, s in local.shortcuts : k => s.from }
}
