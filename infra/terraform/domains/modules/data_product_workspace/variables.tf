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

variable "lakehouse_tag_ids" {
  description = "Fabric tag IDs applied to the lakehouse."
  type        = list(string)
}
