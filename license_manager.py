"""License activation for OI Pulse Dashboard.

One license key binds to one trading account (broker client id). The same account
may run on any number of devices; a different account is rejected. Validation is
online (license.billionitwealth.in) with an offline grace period so a brief internet
outage does not lock out a genuine, already-activated user.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
LICENSE_PATH = Path(os.getenv("OI_PULSE_LICENSE", str(APP_DIR / "license.json")))
LICENSE_URL = os.getenv("OI_PULSE_LICENSE_URL", "https://license.billionitwealth.in").rstrip("/")

REVALIDATE_SECONDS = 6 * 3600        # re-check with the server at most this often
OFFLINE_GRACE_SECONDS = 7 * 86400    # allow this long offline after the last success
# Dev/testing escape hatch — never set this in the shipped build.
DISABLED = os.getenv("OI_PULSE_LICENSE_DISABLE", "") == "1"

_session = {"ok_until": 0.0, "account": None}


def _read() -> dict:
    if LICENSE_PATH.exists():
        try:
            data = json.loads(LICENSE_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {}


def _write(data: dict) -> None:
    LICENSE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_license_key() -> str:
    env = os.getenv("OI_PULSE_LICENSE_KEY", "").strip()
    if env:
        return env
    return str(_read().get("license_key", "")).strip()


def save_license_key(key: str) -> None:
    data = _read()
    data["license_key"] = key.strip()
    _write(data)
    _session["ok_until"] = 0.0  # force a fresh check


def is_set() -> bool:
    return bool(get_license_key())


def _activate(key: str, account_id: str):
    body = json.dumps({"license_key": key, "account_id": account_id}).encode("utf-8")
    req = urllib.request.Request(
        LICENSE_URL + "/api/activate", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as exc:
        try:
            return json.loads(exc.read().decode("utf-8")), None
        except Exception:
            return None, f"HTTP {exc.code}"
    except Exception as exc:
        return None, str(exc)  # unreachable / network error


def ensure_valid(account_id: str) -> None:
    """Raise RuntimeError if the license is missing, rejected, or unverifiable."""
    if DISABLED:
        return
    key = get_license_key()
    if not key:
        raise RuntimeError("No license key set. Enter your license key to activate OI Pulse.")
    account_id = str(account_id).strip()
    now = time.time()
    if _session["account"] == account_id and now < _session["ok_until"]:
        return

    result, _net_err = _activate(key, account_id)
    if result is not None:
        if result.get("ok"):
            _session.update(account=account_id, ok_until=now + REVALIDATE_SECONDS)
            data = _read()
            data["account_id"] = account_id
            data["last_success"] = now
            _write(data)
            return
        raise RuntimeError(result.get("error") or "License validation failed")

    # Server unreachable → allow within the offline grace of the last success.
    data = _read()
    last = float(data.get("last_success", 0) or 0)
    if str(data.get("account_id", "")) == account_id and last and (now - last) < OFFLINE_GRACE_SECONDS:
        _session.update(account=account_id, ok_until=now + 300)
        return
    raise RuntimeError("Could not reach the license server. Please connect to the internet to activate your license.")
