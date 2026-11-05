"""Fabric tenant settings as code (Admin API), for the settings the Terraform provider does not manage.

    uv run tenant-settings           # dry run: show which settings differ from DESIRED; exits 1 on drift
    uv run tenant-settings --apply   # update the ones that differ

Requires the Fabric administrator role (user locally, service principal with write admin APIs in CI).
"""

from __future__ import annotations

import argparse

from fabric_mesh_tools.api import FABRIC, request

API = f"{FABRIC}/admin/tenantsettings"

# settingName -> enabled. Every setting applies to the entire organization.
DESIRED: dict[str, bool] = {
    # Purview Information Protection
    "EimInformationProtectionEdit": True,  # users can apply sensitivity labels to Fabric items
    "EimInformationProtectionDefaultLabelDomainSetting": True,  # domain admins set a default label per domain
    "EimInformationProtectionDownstreamInheritanceSetting": True,  # labels flow to downstream items (lineage)
    # Endorsement
    "CertifyDatasets": True,  # Certified endorsement
    "AllowEndorsementMasterDataSwitch": True,  # Master data endorsement (e.g. dim_station)
    # Data mesh
    "EnableReassignDataDomainSwitch": True,  # tenant/domain admins can move workspaces between domains
}


def diff_settings(desired: dict[str, bool], current: dict[str, dict]) -> dict[str, bool]:
    """settingName => wanted value for every setting that differs. Unknown settings are an error."""
    missing = sorted(set(desired) - set(current))
    if missing:
        raise SystemExit(f"Unknown tenant settings: {', '.join(missing)}")
    return {name: enabled for name, enabled in desired.items() if current[name]["enabled"] != enabled}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--apply", action="store_true", help="update the settings that differ")
    args = parser.parse_args(argv)

    current = {s["settingName"]: s for s in request("GET", API)["tenantSettings"]}
    changes = diff_settings(DESIRED, current)
    for name, enabled in DESIRED.items():
        mark = "change" if name in changes else "ok    "
        print(f"{mark}  {name:<55} {current[name]['enabled']!s:>5} -> {enabled!s:<5}  {current[name]['title']}")

    if not changes:
        print("Tenant settings match DESIRED.")
    elif not args.apply:
        raise SystemExit(f"\n{len(changes)} setting(s) differ. Re-run with --apply to update them.")
    else:
        failed = []
        for name, enabled in changes.items():
            try:
                request("POST", f"{API}/{name}/update", {"enabled": enabled})
                print(f"updated {name} -> {enabled}")
            except SystemExit as exc:  # e.g. label settings are rejected until Purview labels are published
                failed.append(name)
                print(f"FAILED  {exc}")
        if failed:
            raise SystemExit(f"{len(failed)} setting(s) not updated: {', '.join(failed)}")


if __name__ == "__main__":
    main()
