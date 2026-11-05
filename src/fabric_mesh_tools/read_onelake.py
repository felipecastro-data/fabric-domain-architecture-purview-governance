"""Read a lakehouse Delta table over OneLake with delta-rs (Azure CLI user locally, service principal in CI).

    uv run --extra onelake read-onelake <workspace-id> <lakehouse> <table> ["<python statement over dt>"]

Without a statement it prints the last 10 rows; e.g. ``"print(dt.to_pandas().groupby('_period').size())"``.
<lakehouse> is a name or an ID; pass the ID for users without a Fabric license (the lookup API needs one, OneLake
doesn't).

Vendored from felipecastro-data/fabric-medallion-cicd-terraform, tools/read_onelake.py at commit cbbcf4a, with one
deliberate change: ``lakehouse_id`` accepts a GUID and skips the Fabric API lookup, so license-free consumers can be
tested exactly as they read (see the README's "Verified as a real consumer").
"""

from __future__ import annotations

import re
import sys

from fabric_mesh_tools.api import FABRIC, request

STORAGE_SCOPE = "https://storage.azure.com/.default"
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)


def lakehouse_id(ws: str, lakehouse: str) -> str:
    if GUID.match(lakehouse):
        return lakehouse
    items = request("GET", f"{FABRIC}/workspaces/{ws}/lakehouses")["value"]
    return next(x["id"] for x in items if x["displayName"] == lakehouse)


def table_uri(ws: str, lakehouse: str, table: str) -> str:
    return f"abfss://{ws}@onelake.dfs.fabric.microsoft.com/{lakehouse_id(ws, lakehouse)}/Tables/dbo/{table}"


def open_table(ws: str, lakehouse: str, table: str):
    from deltalake import DeltaTable  # optional dependency: uv sync --extra onelake

    from fabric_mesh_tools.fabric_auth import access_token

    storage = {"bearer_token": access_token(STORAGE_SCOPE), "use_fabric_endpoint": "true"}
    return DeltaTable(table_uri(ws, lakehouse, table), storage_options=storage)


def main(argv: list[str] | None = None) -> None:
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 3:
        raise SystemExit(__doc__)
    dt = open_table(*args[:3])
    if len(args) > 3:
        exec(args[3])  # noqa: S102 - ad-hoc inspection statement over `dt` (local verification tool)
    else:
        print(dt.to_pandas().tail(10).to_string())


if __name__ == "__main__":
    main()
