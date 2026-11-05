from fabric_mesh_tools.workspace_domains import diff_assignments

PROD, DEV = r"^mesh-[a-z0-9]+$", r"^mesh-[a-z0-9]+-dev$"
DESIRED = {
    "mobility": {"workspace_id": "w1", "domain_id": "d-mobility"},
    "weather": {"workspace_id": "w2", "domain_id": "d-weather"},
}


def test_matching_assignments():
    live = {
        "w1": {"name": "mesh-mobility", "domainId": "d-mobility"},
        "w2": {"name": "mesh-weather", "domainId": "d-weather"},
    }
    assert {s for s, _ in diff_assignments(DESIRED, PROD, live)} == {"ok"}


def test_reassigned_and_unmanaged_workspaces_drift():
    live = {
        "w1": {"name": "mesh-mobility", "domainId": "d-weather"},
        "w2": {"name": "mesh-weather", "domainId": "d-weather"},
        "w9": {"name": "mesh-sandbox", "domainId": None},
        "w8": {"name": "divvy-medallion-prod", "domainId": None},
    }
    drift = [m for s, m in diff_assignments(DESIRED, PROD, live) if s == "DRIFT"]
    assert len(drift) == 2
    assert drift[0].startswith("mobility")
    assert "mesh-sandbox" in drift[1]


def test_other_environments_are_not_unmanaged():
    live = {
        "w1": {"name": "mesh-mobility", "domainId": "d-mobility"},
        "w2": {"name": "mesh-weather", "domainId": "d-weather"},
        "w3": {"name": "mesh-mobility-dev", "domainId": "d-mobility"},
    }
    assert {s for s, _ in diff_assignments(DESIRED, PROD, live)} == {"ok"}
    dev = {"mobility": {"workspace_id": "w3", "domain_id": "d-mobility"}}
    lines = diff_assignments(dev, DEV, live)
    assert lines == [("ok", "mobility   d-mobility -> d-mobility")]
