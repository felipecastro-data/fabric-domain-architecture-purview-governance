"""Serving check for the Analytics domain's Direct Lake semantic model (Terraform output `semantic_models`).

    MESH_ENV=dev uv run semantic-model --refresh   # frame the model on the current Delta versions, then query it
    uv run semantic-model                          # query only; exits 1 when the model returns no demand

Framing (a "Full" refresh) points a Direct Lake model at the latest Delta versions; no data is imported. The check
then runs a DAX query through the Power BI executeQueries API, the same endpoint reports and DAX clients use, so a
passing run proves the model is reachable and computes its measures through the shortcut chain.

executeQueries rejects service principals on SSO models, and Direct Lake on OneLake always queries as the caller.
In CI (the service principal) the check is the latest framing instead: it must be Completed, which proves the model
binds to the current Delta schemas through the shortcut chain. Run it as a user for the DAX values.
"""

from __future__ import annotations

import argparse
import time

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import POWERBI_SCOPE, request
from fabric_mesh_tools.fabric_auth import in_github_actions

POWERBI = "https://api.powerbi.com/v1.0/myorg"
MEASURES = [
    "Trips",
    "Days",
    "Trips per day",
    "Trips per dry day",
    "Trips per wet day",
    "Wet-day demand change",
    "Member share",
]


def query() -> str:
    columns = ", ".join(f'"{m}", [{m}]' for m in MEASURES)
    return f"EVALUATE ROW ( {columns} )"


def parse(result: dict) -> dict[str, float | None]:
    """Measure => value from an executeQueries response (columns come back as '[Name]')."""
    row = result["results"][0]["tables"][0]["rows"][0]
    return {key.strip("[]"): value for key, value in row.items()}


def problems(values: dict[str, float | None]) -> list[str]:
    found = [f"{m} is blank" for m in MEASURES if values.get(m) is None]
    if not found and values["Trips"] <= 0:
        found.append("no trips")
    return found


def refreshes_url(workspace_id: str, model_id: str) -> str:
    return f"{POWERBI}/groups/{workspace_id}/datasets/{model_id}/refreshes"


def last_framing(workspace_id: str, model_id: str) -> str:
    """Status of the latest refresh: Completed, Failed, Disabled, Unknown (in progress) or Never."""
    history = request("GET", f"{refreshes_url(workspace_id, model_id)}?$top=1", scope=POWERBI_SCOPE)["value"]
    return history[0]["status"] if history else "Never"


def refresh(workspace_id: str, model_id: str, timeout_s: int = 600) -> str:
    request("POST", refreshes_url(workspace_id, model_id), {"type": "Full"}, POWERBI_SCOPE)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        status = last_framing(workspace_id, model_id)
        if status != "Unknown":  # Unknown = in progress
            return status
        time.sleep(5)
    raise SystemExit(f"framing {model_id} did not finish within {timeout_s} s")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true", help="frame the model before querying it")
    args = parser.parse_args(argv)

    failures = 0
    for domain, m in sorted(terraform.output(terraform.DOMAINS_STACK, "semantic_models").items()):
        if args.refresh:
            started = time.time()
            status = refresh(m["workspace_id"], m["id"])
            print(f"{domain:<10} {m['name']}: framing {status} in {time.time() - started:.0f} s")
            if status != "Completed":
                failures += 1
                continue
        if in_github_actions():  # service principal: executeQueries is not available, check the framing
            status = last_framing(m["workspace_id"], m["id"])
            failures += status != "Completed"
            print(
                f"{domain:<10} {m['name']}: {'ok' if status == 'Completed' else 'FAIL'} (last framing {status}; "
                "DAX values need a user identity)"
            )
            continue
        started = time.time()
        result = request(
            "POST",
            f"{POWERBI}/groups/{m['workspace_id']}/datasets/{m['id']}/executeQueries",
            {"queries": [{"query": query()}], "serializerSettings": {"includeNulls": True}},
            POWERBI_SCOPE,
        )
        values, elapsed = parse(result), time.time() - started
        found = problems(values)
        failures += bool(found)
        print(f"{domain:<10} {m['name']}: {'FAIL' if found else 'ok'} (DAX query {elapsed:.1f} s)")
        for name, value in values.items():
            shown = f"{value:,.3f}" if isinstance(value, float) else f"{value:,}" if isinstance(value, int) else value
            print(f"           {name:<24} {shown}")
        for p in found:
            print(f"           problem: {p}")
    if failures:
        raise SystemExit(f"\n{failures} semantic model check(s) failed.")


if __name__ == "__main__":
    main()
