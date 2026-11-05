# OneLake security: read roles on the data product lakehouses (whole lakehouse) and on the upstream source lakehouses
# (table level). Workspace Admins/Contributors (owners, engineers) bypass roles in their own workspace; everyone else
# needs a role at every shortcut hop, so the source roles decide which tables Viewers and other domains can read.
#
# Terraform owns the role definitions and renders them as Fabric API bodies; src/fabric_mesh_tools/onelake_roles.py applies them.
# fabric_onelake_data_access_security (provider 1.14) fails after every apply with Entra members because the API
# omits objectType (microsoft/terraform-provider-fabric#1044). Switch back to the resource once the fix ships.

locals {
  access_roles = {
    for k, r in var.access_roles : k => merge(r, {
      lakehouse = split(".", k)[0]
      role_name = split(".", k)[1]
    })
  }
}

# The first apply through the resource left 4 roles tainted in state; forget them, keep them in Fabric
removed {
  from = fabric_onelake_data_access_security.this

  lifecycle {
    destroy = false
  }
}

output "onelake_access_roles" {
  description = "\"<lakehouse>.<RoleName>\" => { workspace_id, item_id, role } — applied by src/fabric_mesh_tools/onelake_roles.py."
  value = {
    for k, r in local.access_roles : k => {
      workspace_id = local.shortcut_sources[r.lakehouse].workspace_id
      item_id      = local.shortcut_sources[r.lakehouse].item_id
      role = {
        name = r.role_name
        decisionRules = [{
          effect = "Permit"
          permission = [
            { attributeName = "Action", attributeValueIncludedIn = ["Read"] },
            { attributeName = "Path", attributeValueIncludedIn = [for t in r.tables : t == "*" ? "*" : "/Tables/dbo/${t}"] },
          ]
        }]
        members = {
          microsoftEntraMembers = [for g in r.groups : {
            objectId   = local.groups[g]
            objectType = "Group"
            tenantId   = data.terraform_remote_state.governance.outputs.tenant_id
          }]
        }
      }
    }
  }
}
