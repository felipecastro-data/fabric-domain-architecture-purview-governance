"""JSON over HTTPS for the Fabric and Power BI REST APIs, with the repo's token handling."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

from fabric_mesh_tools.fabric_auth import access_token

FABRIC = "https://api.fabric.microsoft.com/v1"
POWERBI_SCOPE = "https://analysis.windows.net/powerbi/api/.default"


def request(
    method: str, url: str, body: dict | None = None, scope: str | None = None, attempts: int = 3
) -> dict | None:
    """Send one request. HTTP errors exit with the response body (never retried: they are not transient);
    connection failures are retried ``attempts`` times, 5 s apart."""
    data = json.dumps(body).encode() if body is not None else None
    token = access_token(scope) if scope else access_token()
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    for attempt in range(attempts):
        try:
            req = urllib.request.Request(url, data=data, method=method, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as response:  # noqa: S310 - fixed https API hosts
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as exc:
            raise SystemExit(f"{method} {url} -> {exc.code} {exc.read().decode()}") from exc
        except urllib.error.URLError:
            if attempt == attempts - 1:
                raise
            time.sleep(5)
    return None
