"""Render the README charts: effective table access per group, and the data the shortcuts serve in place.

    uv run --no-project --with deltalake --with pyarrow --with matplotlib \\
        python tools/mesh_charts.py --out docs/charts

Access comes from Terraform outputs (shortcuts, OneLake roles, groups). Shortcuts are passthrough, so a group reads a
table only with a role at every hop: its own domain's lakehouse (workspace role, built-in DefaultReader), then
`CrossDomainRead` on each producer, then a table role on the source lakehouse. Sizes are the current Delta snapshot of
each source table, read over OneLake.

Palette: the dataviz reference instance (status good/critical with icon + label, categorical slot 1), light surface.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pyarrow as pa  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from read_onelake import open_table  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DOMAINS_STACK = ROOT / "infra" / "terraform" / "domains"
GOVERNANCE_STACK = ROOT / "infra" / "terraform" / "governance"

SURFACE, TEXT, TEXT_2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#a3a29c", "#e4e3df"
GOOD, CRITICAL, BAR = "#0ca30c", "#d03b3b", "#2a78d6"
DOMAINS = ["mobility", "weather", "analytics"]
KINDS = ["owners", "engineers", "consumers"]
TABLES = ["fact_trips", "dim_station", "dim_date", "agg_daily_kpis", "agg_station_monthly", "dim_weather", "weather_daily"]


def tf_output(stack: Path, name: str):
    out = subprocess.run(
        ["terraform", f"-chdir={stack}", "output", "-json", name], check=True, capture_output=True, text=True
    ).stdout
    return json.loads(out)


def role_grants(roles: dict, groups: dict) -> dict[str, list[tuple[set[str], str]]]:
    """Lakehouse key ("mobility", "source:lh_gold") -> [(group keys, path)] for every Permit rule."""
    by_id = {v: k for k, v in groups.items()}
    grants: dict[str, list[tuple[set[str], str]]] = {}
    for key, r in roles.items():
        lakehouse = key.rsplit(".", 1)[0]
        members = {by_id[m["objectId"]] for m in r["role"]["members"]["microsoftEntraMembers"]}
        for rule in r["role"]["decisionRules"]:
            for perm in rule["permission"]:
                if perm["attributeName"] == "Path":
                    grants.setdefault(lakehouse, []).extend((members, p) for p in perm["attributeValueIncludedIn"])
    return grants


def can_read(group: str, lakehouse: str, table: str, shortcuts: dict, grants: dict) -> bool:
    """Follow the shortcut chain from `lakehouse` and require a role at every hop after the group's own lakehouse."""
    target = shortcuts[f"{lakehouse}.{table}"]
    while True:
        paths = {p for members, p in grants.get(target, []) if group in members}
        if "*" not in paths and f"/Tables/dbo/{table}" not in paths:
            return False
        if target.startswith("source:"):
            return True
        target = shortcuts[f"{target}.{table}"]


def resolve_source(lakehouse: str, table: str, shortcuts: dict) -> str:
    target = shortcuts[f"{lakehouse}.{table}"]
    while not target.startswith("source:"):
        target = shortcuts[f"{target}.{table}"]
    return target


def _title(fig, title: str, subtitle: str, y: float = 0.965) -> None:
    fig.set_facecolor(SURFACE)
    fig.text(0.012, y, title, fontsize=13, fontweight="bold", color=TEXT, ha="left", va="top")
    fig.text(0.012, y - 0.055, subtitle, fontsize=9.5, color=TEXT_2, ha="left", va="top")


def access_matrix(shortcuts: dict, grants: dict, out: Path) -> None:
    fig, ax = plt.subplots(figsize=(11, 6.4), dpi=150)
    _title(fig, "Who can read which table", "Effective OneLake access through each group's own data product · "
           "computed from Terraform: a role is needed at every shortcut hop")
    ax.set_facecolor(SURFACE)
    ax.set_xlim(-0.5, len(TABLES) - 0.5)
    rows = [(d, k) for d in DOMAINS for k in KINDS]
    ax.set_ylim(len(rows) - 0.5, -0.5)
    for y, (domain, kind) in enumerate(rows):
        for x, table in enumerate(TABLES):
            if f"{domain}.{table}" not in shortcuts:
                ax.text(x, y, "·", ha="center", va="center", fontsize=12, color=MUTED)
                continue
            ok = can_read(f"{domain}-{kind}", domain, table, shortcuts, grants)
            ax.add_patch(FancyBboxPatch(
                (x - 0.42, y - 0.36), 0.84, 0.72, boxstyle="round,pad=0,rounding_size=0.08",
                facecolor=GOOD if ok else SURFACE, edgecolor=GOOD if ok else CRITICAL, linewidth=1.2,
            ))
            ax.text(x, y, "✓ read" if ok else "✕ denied", ha="center", va="center", fontsize=8.5,
                    fontweight="bold", color="white" if ok else CRITICAL)
    for y in (2.5, 5.5):
        ax.axhline(y, color=GRID, linewidth=1)
    ax.set_xticks(range(len(TABLES)), TABLES, fontsize=8.5, color=TEXT_2)
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(rows)), [f"{d} {k}" for d, k in rows], fontsize=9, color=TEXT_2)
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    fig.text(0.012, 0.03, "·  not a data product of that domain        Owners are workspace Admins, but hold no "
             "role upstream: admin rights don't reach across shortcuts.", fontsize=8.5, color=TEXT_2)
    fig.subplots_adjust(left=0.17, right=0.99, top=0.78, bottom=0.08)
    fig.savefig(out / "access-matrix.png", facecolor=SURFACE)
    plt.close(fig)


def served_in_place(shortcuts: dict, roles: dict, out: Path) -> None:
    sources = {k.rsplit(".", 1)[0]: (r["workspace_id"], r["item_id"]) for k, r in roles.items() if k.startswith("source:")}
    stats: dict[tuple[str, str], tuple[int, int]] = {}
    for lakehouse_table in shortcuts:
        lakehouse, table = lakehouse_table.split(".", 1)
        source = resolve_source(lakehouse, table, shortcuts)
        if (source, table) not in stats:
            adds = pa.table(open_table(*sources[source], table).get_add_actions(flatten=True)).to_pydict()
            stats[(source, table)] = (sum(adds["size_bytes"]), sum(n or 0 for n in adds["num_records"]))
    per_lakehouse = []
    for domain in DOMAINS:
        keys = [k.split(".", 1)[1] for k in shortcuts if k.startswith(f"{domain}.")]
        size = sum(stats[(resolve_source(domain, t, shortcuts), t)][0] for t in keys)
        rows = sum(stats[(resolve_source(domain, t, shortcuts), t)][1] for t in keys)
        per_lakehouse.append((f"lh_{domain}", size / 1e6, rows, len(keys)))
    per_lakehouse.sort(key=lambda r: r[1])
    total = sum(r[1] for r in per_lakehouse)

    fig, ax = plt.subplots(figsize=(11, 3.9), dpi=150)
    _title(fig, f"{total:,.0f} MB served in place, 0 bytes copied",
           f"Delta data a copy-based mesh would duplicate into each data product · {len(shortcuts)} OneLake "
           "shortcuts read the prod medallion lakehouses instead", y=0.95)
    ax.set_facecolor(SURFACE)
    names = [r[0] for r in per_lakehouse]
    ax.barh(names, [r[1] for r in per_lakehouse], height=0.55, color=BAR)
    for y, (_, mb, rows, n) in enumerate(per_lakehouse):
        ax.text(mb + total * 0.008, y, f"{mb:,.1f} MB · {rows:,} rows · {n} tables", va="center", fontsize=9,
                color=TEXT)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.set_xticks([])
    ax.set_xlim(0, max(r[1] for r in per_lakehouse) * 1.45)
    ax.tick_params(colors=TEXT_2, labelsize=9.5, length=0)
    fig.subplots_adjust(left=0.12, right=0.99, top=0.7, bottom=0.08)
    fig.savefig(out / "served-in-place.png", facecolor=SURFACE)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "docs" / "charts")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    shortcuts = tf_output(DOMAINS_STACK, "shortcuts")
    roles = tf_output(DOMAINS_STACK, "onelake_access_roles")
    grants = role_grants(roles, tf_output(GOVERNANCE_STACK, "groups"))
    access_matrix(shortcuts, grants, args.out)
    served_in_place(shortcuts, roles, args.out)


if __name__ == "__main__":
    main()
