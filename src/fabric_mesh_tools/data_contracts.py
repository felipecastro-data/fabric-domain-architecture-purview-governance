"""Data contracts as code: one ODCS v3.1 contract per data product in ``contracts/``, checked against the live tables.

    uv run --extra onelake data-contracts                      # schema, row counts, lineage; exit 1 on drift
    uv run --extra onelake data-freshness                      # each contract's latency SLA; exit 1 when stale
    uv run --extra onelake data-contracts --scaffold mobility  # print a contract skeleton from the live tables

``data-contracts`` (required ``compliance`` check):

* the contract is valid against the vendored ODCS JSON schema;
* every contracted column exists with the same Delta type (missing or retyped = breaking; new columns are reported);
* ``rowCount`` quality rules hold, from the Delta log statistics (no table scan);
* lineage: following each table's OneLake shortcuts ends in the environment's source workspace (Terraform output
  ``source_workspace_name``), which in prod must be the contract's ``sourceWorkspace``.

``MESH_ENV`` (dev | prod, default prod) selects the environment.

``data-freshness`` (separate, non-required job): the newest Delta commit across a product's tables is younger than the
contract's ``latency`` SLA. It alerts on a stale upstream without blocking mesh PRs, which cannot fix it.

Tables are read through the data product lakehouse, so every check also exercises the shortcut chain.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml

from fabric_mesh_tools import terraform
from fabric_mesh_tools.api import FABRIC, request

CONTRACTS = terraform.ROOT / "contracts"
ODCS_SCHEMA = CONTRACTS / "schema" / "odcs-json-schema-v3.1.0.json"
UNITS = {"d": "days", "day": "days", "days": "days", "h": "hours", "hour": "hours", "hours": "hours"}
LOGICAL = {
    "string": "string",
    "byte": "integer",
    "short": "integer",
    "integer": "integer",
    "long": "integer",
    "float": "number",
    "double": "number",
    "boolean": "boolean",
    "date": "date",
    "timestamp": "timestamp",
    "timestamp_ntz": "timestamp",
}


# ---- contracts (pure) -------------------------------------------------------------------------------------------


def load_contracts(directory: Path = CONTRACTS) -> dict[str, dict]:
    """File name => contract, for every contracts/*.yml."""
    return {p.name: yaml.safe_load(p.read_text()) for p in sorted(directory.glob("*.yml"))}


def validate(contract: dict, schema_path: Path = ODCS_SCHEMA) -> list[str]:
    """ODCS JSON-schema errors, as 'path: message'."""
    from jsonschema import Draft201909Validator

    validator = Draft201909Validator(json.loads(schema_path.read_text()))
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}" for e in validator.iter_errors(contract)]


def custom(obj: dict, name: str):
    return next((c["value"] for c in obj.get("customProperties", []) if c["property"] == name), None)


def expected_columns(table: dict) -> dict[str, str]:
    """Column => Delta type declared in one schema object."""
    return {p["physicalName"] if "physicalName" in p else p["name"]: p["physicalType"] for p in table["properties"]}


def min_rows(table: dict) -> int | None:
    """The table's rowCount rule as an exclusive lower bound (mustBeGreaterThan / mustBeGreaterOrEqualTo)."""
    for rule in table.get("quality", []):
        if rule.get("metric") == "rowCount":
            if "mustBeGreaterThan" in rule:
                return int(rule["mustBeGreaterThan"])
            if "mustBeGreaterOrEqualTo" in rule:
                return int(rule["mustBeGreaterOrEqualTo"]) - 1
    return None


def latency(contract: dict) -> timedelta | None:
    for sla in contract.get("slaProperties", []):
        if sla["property"] == "latency":
            return timedelta(**{UNITS[sla.get("unit", "d").lower()]: float(sla["value"])})
    return None


@dataclass
class SchemaDiff:
    breaking: list[str] = field(default_factory=list)
    additive: list[str] = field(default_factory=list)


def diff_schema(expected: dict[str, str], live: dict[str, str]) -> SchemaDiff:
    diff = SchemaDiff()
    for col, typ in expected.items():
        if col not in live:
            diff.breaking.append(f"{col} missing")
        elif live[col] != typ:
            diff.breaking.append(f"{col} {typ} -> {live[col]}")
    diff.additive = [f"{col} {typ} (new)" for col, typ in live.items() if col not in expected]
    return diff


def follow_shortcuts(start: tuple[str, str], table: str, lookup) -> list[tuple[str, str]]:
    """[(workspace, item)] from `start` to where `table` is stored. ``lookup(ws, item, name)`` returns the shortcut's
    OneLake target dict (workspaceId, itemId, path) or None when the table is not a shortcut there."""
    chain, here, name = [start], start, table
    for _ in range(10):  # OneLake allows at most 10 shortcuts in a path
        target = lookup(*here, name)
        if target is None:
            return chain
        here, name = (target["workspaceId"], target["itemId"]), target["path"].rsplit("/", 1)[-1]
        chain.append(here)
    raise SystemExit(f"{table}: more than 10 shortcut hops from {start}")


def expected_source(contracted: str | None, env: str, env_source: str) -> str:
    """The workspace lineage must end in. The contract states prod's source; other environments read their own."""
    if env == "prod" and contracted and contracted != env_source:
        raise SystemExit(f"Contract sourceWorkspace {contracted} differs from Terraform's prod source {env_source}")
    return env_source


def stale(last_commit: datetime, max_age: timedelta, now: datetime) -> bool:
    return now - last_commit > max_age


# ---- live state -------------------------------------------------------------------------------------------------


@dataclass
class LiveTable:
    columns: dict[str, str]
    rows: int
    last_commit: datetime


def live_table(workspace_id: str, item_id: str, table: str) -> LiveTable:
    import pyarrow as pa

    from fabric_mesh_tools.read_onelake import open_table

    dt = open_table(workspace_id, item_id, table)
    fields = json.loads(dt.schema().to_json())["fields"]
    adds = pa.table(dt.get_add_actions(flatten=True)).to_pydict()
    committed = datetime.fromtimestamp(dt.history(1)[0]["timestamp"] / 1000, tz=UTC)
    return LiveTable(
        columns={f["name"]: f["type"] if isinstance(f["type"], str) else f["type"]["type"] for f in fields},
        rows=sum(n or 0 for n in adds["num_records"]),
        last_commit=committed,
    )


class Shortcuts:
    """OneLake shortcut lookup with one list call per item, and workspace / item names for messages."""

    def __init__(self) -> None:
        self._items: dict[tuple[str, str], dict[str, dict]] = {}
        self._names: dict[str, str] = {}

    def __call__(self, workspace_id: str, item_id: str, name: str) -> dict | None:
        key = (workspace_id, item_id)
        if key not in self._items:
            url = f"{FABRIC}/workspaces/{workspace_id}/items/{item_id}/shortcuts"
            listed = []
            while url:
                page = request("GET", url)
                listed += page["value"]
                url = page.get("continuationUri")
            self._items[key] = {
                s["name"]: s["target"]["oneLake"]
                for s in listed
                if s["path"].strip("/") == "Tables/dbo" and s["target"]["type"] == "OneLake"
            }
        return self._items[key].get(name)

    def workspace_name(self, workspace_id: str) -> str:
        if workspace_id not in self._names:
            self._names[workspace_id] = request("GET", f"{FABRIC}/workspaces/{workspace_id}")["displayName"]
        return self._names[workspace_id]

    def item_name(self, workspace_id: str, item_id: str) -> str:
        if item_id not in self._names:
            self._names[item_id] = request("GET", f"{FABRIC}/workspaces/{workspace_id}/items/{item_id}")["displayName"]
        return self._names[item_id]


def products() -> dict[str, dict]:
    return terraform.output(terraform.DOMAINS_STACK, "workspaces")


# ---- commands ---------------------------------------------------------------------------------------------------


def check(contracts: dict[str, dict]) -> int:
    """Validate and check every contract; returns the number of failures."""
    workspaces, shortcuts, failures = products(), Shortcuts(), 0
    env = terraform.environment()
    env_source = terraform.output(terraform.DOMAINS_STACK, "source_workspace_name")
    for file, contract in contracts.items():
        print(f"== {file}  ({contract['domain']} · {contract['dataProduct']} · v{contract['version']})")
        errors = validate(contract)
        for e in errors:
            print(f"   INVALID  {e}")
        failures += len(errors)
        product = workspaces[contract["domain"]]
        start = (product["workspace_id"], product["lakehouse_id"])
        source = expected_source(custom(contract, "sourceWorkspace"), env, env_source)
        for table in contract["schema"]:
            name = table["physicalName"] if "physicalName" in table else table["name"]
            live = live_table(*start, name)
            diff = diff_schema(expected_columns(table), live.columns)
            floor = min_rows(table)
            chain = follow_shortcuts(start, name, shortcuts)
            ends_in = shortcuts.workspace_name(chain[-1][0])
            problems = [*diff.breaking]
            if floor is not None and live.rows <= floor:
                problems.append(f"rowCount {live.rows:,} <= {floor:,}")
            if source and ends_in != source:
                problems.append(f"lineage ends in {ends_in}, contract says {source}")
            path = " -> ".join(shortcuts.item_name(*hop) for hop in chain)
            status = "FAIL" if problems else "ok  "
            print(f"   {status}  {name:<20} {len(live.columns):>2} cols  {live.rows:>10,} rows  {path} @ {ends_in}")
            for p in problems:
                print(f"         breaking: {p}")
            for a in diff.additive:
                print(f"         additive: {a}")
            failures += bool(problems)
    return failures


def freshness(contracts: dict[str, dict], now: datetime | None = None) -> int:
    workspaces, stale_products = products(), 0
    now = now or datetime.now(UTC)
    for file, contract in contracts.items():
        max_age = latency(contract)
        if max_age is None:
            print(f"--    {file}: no latency SLA")
            continue
        product = workspaces[contract["domain"]]
        commits = {
            t.get("physicalName", t["name"]): live_table(
                product["workspace_id"], product["lakehouse_id"], t.get("physicalName", t["name"])
            ).last_commit
            for t in contract["schema"]
        }
        newest = max(commits.values())
        is_stale = stale(newest, max_age, now)
        stale_products += is_stale
        age = now - newest
        print(
            f"{'STALE' if is_stale else 'ok   '} {contract['dataProduct']:<14} "
            f"newest write {newest:%Y-%m-%d %H:%M} UTC "
            f"({age.days} d {age.seconds // 3600} h ago), SLA {max_age.days} d"
        )
        for table, at in sorted(commits.items()):
            print(f"        {table:<20} {at:%Y-%m-%d %H:%M}")
    return stale_products


def scaffold(domain: str) -> dict:
    """A contract skeleton from the live tables of one data product (fill in descriptions and owners)."""
    product = products()[domain]
    shortcuts = terraform.output(terraform.DOMAINS_STACK, "shortcuts")
    tables = sorted(k.split(".", 1)[1] for k in shortcuts if k.startswith(f"{domain}."))
    schema = []
    for table in tables:
        live = live_table(product["workspace_id"], product["lakehouse_id"], table)
        schema.append(
            {
                "name": table,
                "physicalName": table,
                "physicalType": "table",
                "description": "TODO",
                "properties": [
                    {"name": c, "logicalType": LOGICAL.get(t, "string"), "physicalType": t}
                    for c, t in live.columns.items()
                ],
                "quality": [{"type": "library", "metric": "rowCount", "mustBeGreaterThan": 0}],
            }
        )
    return {
        "apiVersion": "v3.1.0",
        "kind": "DataContract",
        "id": f"urn:fabric-mesh:{domain}",
        "name": f"{domain} data product",
        "version": "1.0.0",
        "status": "active",
        "domain": domain,
        "dataProduct": Shortcuts().item_name(product["workspace_id"], product["lakehouse_id"]),
        "schema": schema,
        "slaProperties": [{"property": "latency", "value": 8, "unit": "d"}],
        "customProperties": [{"property": "sourceWorkspace", "value": "divvy-medallion-prod"}],
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scaffold", metavar="DOMAIN", help="print a contract skeleton from the live tables")
    args = parser.parse_args(argv)
    if args.scaffold:
        yaml.safe_dump(scaffold(args.scaffold), sys.stdout, sort_keys=False, width=120)
        return
    failures = check(load_contracts())
    if failures:
        raise SystemExit(f"\n{failures} contract check(s) failed.")
    print("\nData products match their contracts.")


def main_freshness(argv: list[str] | None = None) -> None:
    argparse.ArgumentParser(description="Check each data contract's latency SLA.").parse_args(argv)
    stale_products = freshness(load_contracts())
    if stale_products:
        raise SystemExit(f"\n{stale_products} data product(s) older than their latency SLA.")
    print("\nEvery data product is within its latency SLA.")


if __name__ == "__main__":
    main()
