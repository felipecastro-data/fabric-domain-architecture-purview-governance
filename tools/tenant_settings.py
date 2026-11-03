"""Fabric tenant settings as code (Admin API), for the settings the Terraform provider does not manage.

python tools/tenant_settings.py           # dry run: show which settings differ from DESIRED
python tools/tenant_settings.py --apply   # update the ones that differ

Requires the Fabric administrator role (user locally, service principal with write admin APIs in CI).
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

from fabric_auth import access_token  # fresh GitHub OIDC exchange in CI, az CLI locally

API = "https://api.fabric.microsoft.com/v1/admin/tenantsettings"

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


def req(method: str, url: str, body: dict | None = None) -> dict | None:
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"}
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, method=method, headers=headers), timeout=60) as r:  # noqa: S310
            raw = r.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{method} {url} -> {exc.code} {exc.read().decode()}") from exc


def main(apply: bool) -> None:
    current = {s["settingName"]: s for s in req("GET", API)["tenantSettings"]}
    missing = sorted(set(DESIRED) - set(current))
    if missing:
        raise SystemExit(f"Unknown tenant settings: {', '.join(missing)}")

    changes = {name: enabled for name, enabled in DESIRED.items() if current[name]["enabled"] != enabled}
    for name, enabled in DESIRED.items():
        mark = "change" if name in changes else "ok    "
        print(f"{mark}  {name:<55} {current[name]['enabled']!s:>5} -> {enabled!s:<5}  {current[name]['title']}")

    if not changes:
        print("Tenant settings match DESIRED.")
    elif not apply:
        print(f"\n{len(changes)} setting(s) differ. Re-run with --apply to update them.")
    else:
        failed = []
        for name, enabled in changes.items():
            try:
                req("POST", f"{API}/{name}/update", {"enabled": enabled})
                print(f"updated {name} -> {enabled}")
            except SystemExit as exc:  # e.g. label settings are rejected until Purview labels are published
                failed.append(name)
                print(f"FAILED  {exc}")
        if failed:
            raise SystemExit(f"{len(failed)} setting(s) not updated: {', '.join(failed)}")


if __name__ == "__main__":
    main(apply="--apply" in sys.argv[1:])
