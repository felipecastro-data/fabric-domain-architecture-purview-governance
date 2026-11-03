variable "project_name" {
  description = "Short project name, used as the prefix for every Fabric workspace."
  type        = string
  default     = "mesh"
}

variable "capacity_id" {
  description = "ID of the Fabric capacity that hosts all workspaces."
  type        = string
}

variable "source_workspace_name" {
  description = "Upstream workspace whose Delta tables the producer domains expose (the medallion platform's prod workspace)."
  type        = string
  default     = "divvy-medallion-prod"
}

variable "data_products" {
  description = <<-EOT
    One data product lakehouse per domain (key = domain key from the governance stack).
    Each shortcut maps a table name to its source: `from` is "source:<lakehouse>" for the upstream medallion workspace,
    or another domain key for a cross-domain shortcut.
  EOT
  type = map(object({
    lakehouse   = string
    description = string
    shortcuts = map(object({
      from  = string
      table = string
    }))
  }))
  default = {
    mobility = {
      lakehouse   = "lh_mobility"
      description = "Mobility data product: Divvy trips star schema and KPIs"
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
      shortcuts = {
        dim_weather   = { from = "source:lh_gold", table = "dim_weather" }
        weather_daily = { from = "source:lh_silver", table = "weather_daily" }
      }
    }
    analytics = {
      lakehouse   = "lh_analytics"
      description = "Analytics consumer lakehouse: cross-domain shortcuts to Mobility and Weather data products"
      shortcuts = {
        fact_trips     = { from = "mobility", table = "fact_trips" }
        dim_station    = { from = "mobility", table = "dim_station" }
        dim_date       = { from = "mobility", table = "dim_date" }
        agg_daily_kpis = { from = "mobility", table = "agg_daily_kpis" }
        dim_weather    = { from = "weather", table = "dim_weather" }
      }
    }
  }
}
