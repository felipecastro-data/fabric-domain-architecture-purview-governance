resource "fabric_workspace" "this" {
  display_name = var.display_name
  description  = var.description
  capacity_id  = var.capacity_id
}

# Workspace roles follow the domain's Entra groups. Consumers are Viewers: with OneLake security enabled,
# Viewers only see the tables a OneLake data access role grants them.
locals {
  role_assignments = {
    admin_user = { id = var.admin_user_object_id, type = "User", role = "Admin" }
    owners     = { id = var.group_ids.owners, type = "Group", role = "Admin" }
    engineers  = { id = var.group_ids.engineers, type = "Group", role = "Contributor" }
    consumers  = { id = var.group_ids.consumers, type = "Group", role = "Viewer" }
  }
}

resource "fabric_workspace_role_assignment" "this" {
  for_each = local.role_assignments

  workspace_id = fabric_workspace.this.id
  role         = each.value.role

  principal = {
    id   = each.value.id
    type = each.value.type
  }
}

# The data product lakehouse. It holds only OneLake shortcuts (no copied data), so it is safe to recreate.
resource "fabric_lakehouse" "this" {
  workspace_id = fabric_workspace.this.id
  display_name = var.lakehouse_name
  description  = var.lakehouse_description

  configuration = {
    enable_schemas = true
  }
}
