from fabric_mesh_tools.mesh_charts import can_read, resolve_source, role_grants

SHORTCUTS = {
    "mobility.fact_trips": "source:lh_gold",
    "mobility.dim_station": "source:lh_gold",
    "analytics.fact_trips": "mobility",
    "analytics.dim_station": "mobility",
}
GROUPS = {"analytics-consumers": "g1", "analytics-engineers": "g2", "analytics-owners": "g3"}


def role(paths, *groups):
    return {
        "role": {
            "decisionRules": [{"permission": [{"attributeName": "Path", "attributeValueIncludedIn": paths}]}],
            "members": {"microsoftEntraMembers": [{"objectId": GROUPS[g]} for g in groups]},
        }
    }


ROLES = {
    "mobility.CrossDomainRead": role(["*"], "analytics-consumers", "analytics-engineers"),
    "source:lh_gold.MeshAggregates": role(["/Tables/dbo/dim_station"], "analytics-consumers"),
    "source:lh_gold.MeshRideLevel": role(["/Tables/dbo/fact_trips", "/Tables/dbo/dim_station"], "analytics-engineers"),
}
GRANTS = role_grants(ROLES, GROUPS)


def test_consumer_reads_dimensions_but_not_ride_level_data():
    assert can_read("analytics-consumers", "analytics", "dim_station", SHORTCUTS, GRANTS)
    assert not can_read("analytics-consumers", "analytics", "fact_trips", SHORTCUTS, GRANTS)


def test_engineer_reads_ride_level_data_through_two_hops():
    assert can_read("analytics-engineers", "analytics", "fact_trips", SHORTCUTS, GRANTS)


def test_owner_without_upstream_roles_is_denied():
    assert not can_read("analytics-owners", "analytics", "dim_station", SHORTCUTS, GRANTS)


def test_resolve_source_follows_the_chain():
    assert resolve_source("analytics", "fact_trips", SHORTCUTS) == "source:lh_gold"
