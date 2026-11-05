import pytest

from fabric_mesh_tools import terraform


def test_domains_stack_gets_the_environment_workspace(monkeypatch):
    monkeypatch.setenv("MESH_ENV", "dev")
    monkeypatch.setenv("TF_WORKSPACE", "something-else")
    assert terraform.stack_env(terraform.DOMAINS_STACK)["TF_WORKSPACE"] == "fabric-mesh-domains-dev"
    assert "TF_WORKSPACE" not in terraform.stack_env(terraform.GOVERNANCE_STACK)


def test_default_environment_is_prod(monkeypatch):
    monkeypatch.delenv("MESH_ENV", raising=False)
    assert terraform.stack_env(terraform.DOMAINS_STACK)["TF_WORKSPACE"] == "fabric-mesh-domains"


def test_unknown_environment_fails(monkeypatch):
    monkeypatch.setenv("MESH_ENV", "test")
    with pytest.raises(SystemExit, match="MESH_ENV"):
        terraform.environment()
