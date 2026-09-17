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

    def _generate(self, cred: dict) -> str:
        kite = KiteConnect(api_key=cred["api_key"])
        options = webdriver.ChromeOptions()
        if os.getenv("OI_PULSE_SHOW_LOGIN", "0") != "1":
            options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1280,900")
        driver = webdriver.Chrome(options=options)
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
            driver.quit()
