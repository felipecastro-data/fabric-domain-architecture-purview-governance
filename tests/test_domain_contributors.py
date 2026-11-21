from fabric_mesh_tools.domain_contributors import tenant_wide_contributors


def assignment(role: str, principal_type: str, principal_id: str = "p1") -> dict:
    return {"role": role, "principal": {"id": principal_id, "type": principal_type}}


def test_only_tenant_wide_contributors_are_flagged():
    assignments = [
        assignment("Admin", "Group", "owners"),
        assignment("Contributor", "Group", "engineers"),
        assignment("Contributor", "EntireTenant", "tenant"),
        assignment("Admin", "EntireTenant", "tenant"),
    ]
    assert tenant_wide_contributors(assignments) == [{"id": "tenant", "type": "EntireTenant"}]


def test_group_contributors_only_match():
    assert tenant_wide_contributors([assignment("Contributor", "Group")]) == []
