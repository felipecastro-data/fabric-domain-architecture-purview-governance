import copy
from datetime import UTC, datetime, timedelta

import pytest

from fabric_mesh_tools import data_contracts as dc

CONTRACTS = dc.load_contracts()


def test_every_data_product_has_a_contract():
    assert {c["domain"] for c in CONTRACTS.values()} == {"mobility", "weather", "analytics"}


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_contract_is_valid_odcs(name):
    assert dc.validate(CONTRACTS[name]) == []


@pytest.mark.parametrize("name", sorted(CONTRACTS))
def test_contract_declares_lineage_freshness_and_row_counts(name):
    contract = CONTRACTS[name]
    assert dc.custom(contract, "sourceWorkspace") == "divvy-medallion-prod"
    assert dc.latency(contract) == timedelta(days=8)
    assert all(dc.min_rows(t) == 0 for t in contract["schema"])


def test_invalid_contract_is_reported():
    broken = copy.deepcopy(CONTRACTS["weather.yml"])
    broken["schema"][0]["properties"][0]["logicalType"] = "varchar"
    del broken["id"]
    errors = dc.validate(broken)
    assert any("'id' is a required property" in e for e in errors)
    assert any(e.startswith("schema/0/properties/0/logicalType") for e in errors)


def test_diff_schema_breaking_and_additive():
    diff = dc.diff_schema({"a": "long", "b": "string", "c": "date"}, {"a": "integer", "b": "string", "d": "double"})
    assert diff.breaking == ["a long -> integer", "c missing"]
    assert diff.additive == ["d double (new)"]


def test_min_rows_operators():
    assert dc.min_rows({"quality": [{"metric": "rowCount", "mustBeGreaterThan": 10}]}) == 10
    assert dc.min_rows({"quality": [{"metric": "rowCount", "mustBeGreaterOrEqualTo": 10}]}) == 9
    assert dc.min_rows({"quality": [{"metric": "nullValues", "mustBe": 0}]}) is None


def test_latency_units():
    assert dc.latency({"slaProperties": [{"property": "latency", "value": 36, "unit": "h"}]}) == timedelta(hours=36)
    assert dc.latency({}) is None


def test_follow_shortcuts_through_two_hops():
    links = {
        ("ws-a", "lh-analytics", "fact_trips"): {
            "workspaceId": "ws-m",
            "itemId": "lh-mobility",
            "path": "Tables/dbo/fact_trips",
        },
        ("ws-m", "lh-mobility", "fact_trips"): {
            "workspaceId": "ws-src",
            "itemId": "lh-gold",
            "path": "Tables/dbo/fact_trips",
        },
    }
    chain = dc.follow_shortcuts(("ws-a", "lh-analytics"), "fact_trips", lambda ws, item, n: links.get((ws, item, n)))
    assert chain == [("ws-a", "lh-analytics"), ("ws-m", "lh-mobility"), ("ws-src", "lh-gold")]


def test_follow_shortcuts_renamed_target():
    links = {("w", "i", "trips"): {"workspaceId": "w2", "itemId": "i2", "path": "Tables/dbo/fact_trips"}}
    seen = []

    def lookup(ws, item, name):
        seen.append(name)
        return links.get((ws, item, name))

    assert dc.follow_shortcuts(("w", "i"), "trips", lookup)[-1] == ("w2", "i2")
    assert seen == ["trips", "fact_trips"]


def test_follow_shortcuts_stops_a_cycle():
    with pytest.raises(SystemExit, match="more than 10"):
        dc.follow_shortcuts(
            ("w", "i"), "t", lambda ws, item, n: {"workspaceId": "w", "itemId": "i", "path": "Tables/dbo/t"}
        )


def test_stale():
    now = datetime(2026, 11, 13, tzinfo=UTC)
    assert dc.stale(datetime(2026, 11, 4, tzinfo=UTC), timedelta(days=8), now)
    assert not dc.stale(datetime(2026, 11, 6, tzinfo=UTC), timedelta(days=8), now)
