import copy

import pytest

from fabric_mesh_tools import onelake_roles


def test_normalize_ignores_order_and_object_type(desired_roles, live_roles):
    desired = desired_roles["mobility.CrossDomainRead"]["role"]
    live = live_roles[("ws-mobility", "lh-mobility")]["CrossDomainRead"]
    assert onelake_roles.normalize(desired) == onelake_roles.normalize(live)


def test_normalize_sees_a_changed_table(desired_roles, live_roles):
    desired = desired_roles["source:lh_gold.MeshAggregates"]["role"]
    live = live_roles[("ws-source", "lh-gold")]["MeshAggregates"]
    assert onelake_roles.normalize(desired) != onelake_roles.normalize(live)


def test_normalize_sees_a_removed_member(desired_roles):
    role = desired_roles["mobility.CrossDomainRead"]["role"]
    fewer = copy.deepcopy(role)
    fewer["members"]["microsoftEntraMembers"].pop()
    assert onelake_roles.normalize(role) != onelake_roles.normalize(fewer)


def test_plan_classifies_ok_update_create_and_unmanaged(desired_roles, live_roles):
    result = onelake_roles.plan(desired_roles, live_roles)
    assert result.states == {
        "mobility.CrossDomainRead": "ok",
        "source:lh_gold.MeshAggregates": "update",
        "source:lh_gold.MeshRideLevel": "create",
    }
    assert result.changes == ["source:lh_gold.MeshAggregates", "source:lh_gold.MeshRideLevel"]
    assert result.unmanaged == ["ws-mobility/lh-mobility.DefaultReader"]


def test_plan_on_an_item_with_no_roles_creates_everything(desired_roles):
    result = onelake_roles.plan(desired_roles, {})
    assert set(result.states.values()) == {"create"}


@pytest.fixture
def offline(monkeypatch, desired_roles, live_roles):
    """Run main() against the fixtures: no terraform, no network. Returns the POSTed role names."""
    posted = []
    monkeypatch.setattr(onelake_roles.terraform, "output", lambda stack, name: desired_roles)
    monkeypatch.setattr(onelake_roles, "live_roles", lambda items: live_roles)
    monkeypatch.setattr(onelake_roles, "request", lambda method, url, body=None: posted.append(body["name"]))
    return posted


def test_main_dry_run_exits_1_on_drift_and_writes_nothing(offline, capsys):
    with pytest.raises(SystemExit, match="2 role"):
        onelake_roles.main([])
    assert offline == []
    assert "unmanaged  ws-mobility/lh-mobility.DefaultReader" in capsys.readouterr().out


def test_main_apply_upserts_only_changed_roles(offline):
    onelake_roles.main(["--apply"])
    assert offline == ["MeshAggregates", "MeshRideLevel"]


def test_main_passes_when_live_matches(monkeypatch, desired_roles, capsys):
    live = {(r["workspace_id"], r["item_id"]): {} for r in desired_roles.values()}
    for r in desired_roles.values():
        live[(r["workspace_id"], r["item_id"])][r["role"]["name"]] = r["role"]
    monkeypatch.setattr(onelake_roles.terraform, "output", lambda stack, name: desired_roles)
    monkeypatch.setattr(onelake_roles, "live_roles", lambda items: live)
    onelake_roles.main([])
    assert "OneLake roles match Terraform." in capsys.readouterr().out
