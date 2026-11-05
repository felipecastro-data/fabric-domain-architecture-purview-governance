import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def desired_roles() -> dict:
    return load("onelake_roles_desired.json")


@pytest.fixture
def live_roles() -> dict:
    """(workspace, item) => {role name => role}, as onelake_roles.live_roles returns it."""
    raw = load("onelake_roles_live.json")
    return {tuple(k.split("/")): {r["name"]: r for r in roles} for k, roles in raw.items()}
