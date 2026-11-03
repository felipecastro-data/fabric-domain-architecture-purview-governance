variable "domains" {
  description = "Fabric domains of the data mesh. `kind` is producer (publishes data products) or consumer (reads them via shortcuts)."
  type = map(object({
    display_name  = string
    description   = string
    kind          = string
    default_label = string
  }))
  default = {
    mobility = {
      display_name  = "Mobility"
      description   = "Producer domain: Chicago Divvy bike-share trips, stations and daily KPIs (managed by Terraform)"
      kind          = "producer"
      default_label = "Confidential"
    }
    weather = {
      display_name  = "Weather"
      description   = "Producer domain: daily Chicago weather from Open-Meteo (managed by Terraform)"
      kind          = "producer"
      default_label = "Public"
    }
    analytics = {
      display_name  = "Analytics"
      description   = "Consumer domain: cross-domain analysis built on Mobility and Weather data products (managed by Terraform)"
      kind          = "consumer"
      default_label = "Confidential"
    }
  }

  validation {
    condition     = alltrue([for d in values(var.domains) : contains(["producer", "consumer"], d.kind)])
    error_message = "Domain kind must be producer or consumer."
  }
}

variable "group_prefix" {
  description = "Prefix for every Entra security group created by this stack."
  type        = string
  default     = "sg-mesh"
}

variable "admin_user_object_id" {
  description = "Entra object ID of the human administrator, added as owner and member of every owners group."
  type        = string
}

variable "ci_service_principal_object_id" {
  description = "Entra object ID of the CI service principal (GitHub OIDC). Owner of every group and member of every owners group (workspace Admin), so local and CI runs plan the same."
  type        = string
}

variable "sensitivity_label_ids" {
  description = "Purview label display name => label ID. Written by tools/purview/labels.ps1 (labels.auto.tfvars.json, gitignored); empty until labels are published."
  type        = map(string)
  default     = {}
}

variable "tags" {
  description = "Tenant-wide Fabric tags used to classify data products."
  type        = set(string)
  default     = ["Data Product", "Source Aligned", "Consumer Aligned", "Contains Ride Data"]
}
