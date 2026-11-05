variable "project_name" {
  description = "Short project name, used as the prefix for every Fabric workspace."
  type        = string
  default     = "mesh"
}

variable "capacity_id" {
  description = "ID of the Fabric capacity that hosts all workspaces."
  type        = string
}

variable "data_products" {
  description = <<-EOT
    One data product lakehouse per domain (key = domain key from the governance stack).
    Each shortcut maps a table name to its source: `from` is "source:<lakehouse>" for the upstream medallion workspace,
    or another domain key for a cross-domain shortcut. `label` (default: the domain's default label), `tags` and
    `endorsement` (Promoted | Certified, prod only) are applied to the lakehouse by src/fabric_mesh_tools/data_product_governance.py.
  EOT
  type = map(object({
    lakehouse   = string
    description = string
    label       = optional(string)
    tags        = list(string)
    endorsement = string
    shortcuts = map(object({
      from  = string
      table = string
    }))
  }))
  default = {
    mobility = {
      lakehouse   = "lh_mobility"
      description = "Mobility data product: Divvy trips star schema and KPIs"
      tags        = ["Data Product", "Source Aligned", "Contains Ride Data"]
      endorsement = "Certified"
      shortcuts = {
        fact_trips          = { from = "source:lh_gold", table = "fact_trips" }
        dim_station         = { from = "source:lh_gold", table = "dim_station" }
        dim_date            = { from = "source:lh_gold", table = "dim_date" }
        agg_daily_kpis      = { from = "source:lh_gold", table = "agg_daily_kpis" }
        agg_station_monthly = { from = "source:lh_gold", table = "agg_station_monthly" }
      }
    }
    weather = {
      lakehouse   = "lh_weather"
      description = "Weather data product: daily Chicago weather"
      tags        = ["Data Product", "Source Aligned"]
      endorsement = "Certified"
      shortcuts = {
        dim_weather   = { from = "source:lh_gold", table = "dim_weather" }
        weather_daily = { from = "source:lh_silver", table = "weather_daily" }
      }
    }
    analytics = {
      lakehouse   = "lh_analytics"
      description = "Analytics consumer lakehouse: cross-domain shortcuts to Mobility and Weather data products"
      tags        = ["Consumer Aligned", "Contains Ride Data"]
      endorsement = "Promoted"
      shortcuts = {
        fact_trips     = { from = "mobility", table = "fact_trips" }
        dim_station    = { from = "mobility", table = "dim_station" }
        dim_date       = { from = "mobility", table = "dim_date" }
        agg_daily_kpis = { from = "mobility", table = "agg_daily_kpis" }
        dim_weather    = { from = "weather", table = "dim_weather" }
      }
    }
  }

  validation {
    condition     = alltrue([for p in values(var.data_products) : contains(["Promoted", "Certified"], p.endorsement)])
    error_message = "endorsement must be Promoted or Certified."
  }
}

variable "access_roles" {
  description = <<-EOT
    OneLake security roles ("<lakehouse>.<RoleName>" => role). `lakehouse` is a domain key or "source:<lakehouse>"
    for the upstream workspace. `tables` are table names under Tables/dbo ("*" = everything); `groups` are governance
    group keys. Shortcuts are passthrough: a reader needs a role at every hop, and access is the intersection.
    Fabric rejects roles on shortcut paths, and every mesh table is a shortcut, so mesh lakehouses grant "*" and
    table-level restrictions live on the source lakehouses, where the data is.
  EOT
  type = map(object({
    tables = list(string)
    groups = list(string)
  }))
  default = {
    # Cross-domain readers pass through the producer lakehouses; the source roles decide which tables they see
    "mobility.CrossDomainRead" = { tables = ["*"], groups = ["analytics-consumers", "analytics-engineers"] }
    "weather.CrossDomainRead"  = { tables = ["*"], groups = ["analytics-consumers", "analytics-engineers"] }

    # Upstream medallion workspace: ride-level fact_trips (Confidential) is for engineers only
    "source:lh_gold.MeshAggregates" = { tables = ["dim_station", "dim_date", "agg_daily_kpis", "agg_station_monthly"], groups = ["mobility-consumers", "analytics-consumers"] }
    "source:lh_gold.MeshRideLevel"  = { tables = ["fact_trips", "dim_station", "dim_date", "agg_daily_kpis", "agg_station_monthly"], groups = ["mobility-engineers", "analytics-engineers"] }
    "source:lh_gold.MeshWeather"    = { tables = ["dim_weather"], groups = ["weather-consumers", "weather-engineers", "analytics-consumers", "analytics-engineers"] }
    "source:lh_silver.MeshWeather"  = { tables = ["weather_daily"], groups = ["weather-consumers", "weather-engineers"] }
  }

  validation {
    condition     = alltrue([for k, r in var.access_roles : startswith(k, "source:") || r.tables == tolist(["*"])])
    error_message = "Mesh lakehouses hold only shortcuts, and Fabric rejects roles on shortcut paths: use tables = [\"*\"] and restrict tables on the source lakehouse."
  }
}
