variable "display_name" {
  description = "Workspace display name."
  type        = string
}

variable "description" {
  description = "Workspace description."
  type        = string
}

variable "capacity_id" {
  description = "Fabric capacity ID the workspace is assigned to."
  type        = string
}

variable "admin_user_object_id" {
  description = "Entra object ID of the user granted the Admin role."
  type        = string
}

variable "group_ids" {
  description = "Entra group object IDs of the domain."
  type = object({
    owners    = string
    engineers = string
    consumers = string
  })
}

variable "lakehouse_name" {
  description = "Name of the data product lakehouse."
  type        = string
}

variable "lakehouse_description" {
  description = "Description of the data product lakehouse."
  type        = string
}
