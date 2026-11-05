import pytest

from fabric_mesh_tools.tenant_settings import diff_settings


def test_only_differing_settings_are_changed():
    current = {"A": {"enabled": True}, "B": {"enabled": False}}
    assert diff_settings({"A": True, "B": True}, current) == {"B": True}


def test_unknown_setting_fails():
    with pytest.raises(SystemExit, match="Unknown tenant settings: C"):
        diff_settings({"C": True}, {"A": {"enabled": True}})
