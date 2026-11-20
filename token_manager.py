from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pyotp
from kiteconnect import KiteConnect
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class TokenManager:
    def __init__(self, credentials_path: Path, database_path: Path):
        self.credentials_path = credentials_path
        self.database_path = database_path
        self._clients: dict[str, KiteConnect] = {}

    def accounts(self) -> list[str]:
        if not self.credentials_path.exists():
            return []
        with self.credentials_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return sorted(str(k).upper() for k, v in data.items() if isinstance(v, dict))

    def credentials(self, zerodha_id: str) -> dict:
        if not self.credentials_path.exists():
            raise RuntimeError(f"Credentials file not found: {self.credentials_path}")
        with self.credentials_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        match = next((v for k, v in data.items() if str(k).upper() == zerodha_id.upper()), None)
        if not isinstance(match, dict):
            raise RuntimeError(f"Zerodha ID {zerodha_id} not found in {self.credentials_path.name}")
        required = ("api_key", "api_secret", "username", "password", "totp_secret")
        missing = [key for key in required if not str(match.get(key, "")).strip()]
        if missing:
            raise RuntimeError("Missing credential fields: " + ", ".join(missing))
        return match

    def _saved_token(self, zerodha_id: str) -> str | None:
        with sqlite3.connect(self.database_path) as conn:
            row = conn.execute("SELECT access_token FROM token_sessions WHERE zerodha_id=?", (zerodha_id.upper(),)).fetchone()
        return row[0] if row else None

    def _save_token(self, zerodha_id: str, token: str) -> None:
        now = datetime.now().isoformat()
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("""INSERT INTO token_sessions(zerodha_id,access_token,generated_at,validated_at)
                VALUES(?,?,?,?) ON CONFLICT(zerodha_id) DO UPDATE SET
                access_token=excluded.access_token,generated_at=excluded.generated_at,
                validated_at=excluded.validated_at""", (zerodha_id.upper(), token, now, now))

    def _mark_valid(self, zerodha_id: str) -> None:
        with sqlite3.connect(self.database_path) as conn:
            conn.execute("UPDATE token_sessions SET validated_at=? WHERE zerodha_id=?", (datetime.now().isoformat(), zerodha_id.upper()))

    def client(self, zerodha_id: str, force_new: bool = False) -> KiteConnect:
        account = zerodha_id.upper()
        if not force_new and account in self._clients:
            return self._clients[account]
        cred = self.credentials(zerodha_id)
        saved = None if force_new else self._saved_token(zerodha_id)
        if saved:
            candidate = KiteConnect(api_key=cred["api_key"])
            candidate.set_access_token(saved)
            try:
                candidate.profile()
                self._mark_valid(zerodha_id)
                self._clients[account] = candidate
                return candidate
            except Exception:
                pass
        token = self._generate(cred)
        self._save_token(zerodha_id, token)
        client = KiteConnect(api_key=cred["api_key"])
        client.set_access_token(token)
        client.profile()
        self._clients[account] = client
        return client

    def _start_chrome(self) -> webdriver.Chrome:
        """Launch Chrome robustly across end-user PCs.

        The bare `webdriver.Chrome(ChromeOptions())` call is fragile: on many Windows
        machines it fails with "session not created: DevToolsActivePort file doesn't
        exist" — Chrome starts but crashes before the driver can attach. The fixes that
        remove that failure are: a throwaway profile dir (so a Chrome the user already
        has open can't cause a "profile in use" clash), --no-sandbox +
        --disable-dev-shm-usage (sandbox/shared-memory crashes), and letting Chrome pick
        the debugging port. We also fall back across headless modes, because
        --headless=new crashes on some older Chrome builds.
        """
        import tempfile

        show_login = os.getenv("OI_PULSE_SHOW_LOGIN", "0") == "1"
        profile_dir = tempfile.mkdtemp(prefix="oi_pulse_chrome_")

        def build_options(headless_mode: str | None) -> webdriver.ChromeOptions:
            opts = webdriver.ChromeOptions()
            if headless_mode:
                opts.add_argument(headless_mode)
            opts.add_argument("--disable-gpu")
            opts.add_argument("--no-sandbox")
            opts.add_argument("--disable-dev-shm-usage")
            opts.add_argument("--remote-debugging-port=0")
            opts.add_argument("--no-first-run")
            opts.add_argument("--no-default-browser-check")
            opts.add_argument("--disable-extensions")
            opts.add_argument(f"--user-data-dir={profile_dir}")
            opts.add_argument("--window-size=1280,900")
            return opts

        # If the user asked to watch the login, go visible only. Otherwise try modern
        # headless, then legacy headless, then a visible window as a last resort — each
        # is a known cure for the DevToolsActivePort launch failure on some machines.
        attempts = [None] if show_login else ["--headless=new", "--headless", None]

        last_error: Exception | None = None
        for mode in attempts:
            try:
                driver = webdriver.Chrome(options=build_options(mode))
                driver._oi_profile_dir = profile_dir  # type: ignore[attr-defined]
                return driver
            except Exception as exc:  # SessionNotCreatedException, WebDriverException…
                last_error = exc
        raise RuntimeError(
            "Could not start Google Chrome for automatic login. Make sure Google Chrome "
            "is installed and up to date (open Chrome → menu → Help → About Google "
            "Chrome to update), then try again. "
            f"Technical details: {last_error}"
        )

    def _generate(self, cred: dict) -> str:
        kite = KiteConnect(api_key=cred["api_key"])
        driver = self._start_chrome()
        wait = WebDriverWait(driver, 30)
        try:
            driver.get(kite.login_url())
            user = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input#userid, input[name='user_id']")))
            password = driver.find_element(By.CSS_SELECTOR, "input#password, input[type='password']")
            user.send_keys(cred["username"])
            password.send_keys(cred["password"])
            driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            otp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "input[autocomplete='one-time-code'], input[label*='TOTP'], input[type='number']")))
            otp.send_keys(pyotp.TOTP(str(cred["totp_secret"]).replace(" ", "")).now())
            try:
                driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
            except Exception:
                pass
            wait.until(lambda d: "request_token=" in d.current_url)
            request_token = parse_qs(urlparse(driver.current_url).query).get("request_token", [None])[0]
            if not request_token:
                raise RuntimeError("request_token was not returned after login")
            return kite.generate_session(request_token, api_secret=cred["api_secret"])["access_token"]
        except Exception as exc:
            raise RuntimeError(f"Automatic Zerodha token generation failed: {exc}") from exc
        finally:
            profile_dir = getattr(driver, "_oi_profile_dir", None)
            try:
                driver.quit()
            except Exception:
                pass
            if profile_dir:
                import shutil
                shutil.rmtree(profile_dir, ignore_errors=True)
