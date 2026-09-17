from __future__ import annotations

import atexit
import json
import os
import sqlite3
import threading
import time
import webbrowser
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from kiteconnect import KiteConnect
from token_manager import TokenManager

APP_DIR = Path(__file__).resolve().parent
DB_PATH = APP_DIR / "oi_pulse.db"
CREDENTIALS_PATH = Path(os.getenv("OI_PULSE_CREDENTIALS", APP_DIR / "zerodha_credentials.json"))
HOST, PORT = "127.0.0.1", 5069
EXCHANGE = {"NIFTY": "NFO", "SENSEX": "BFO"}
INDEX_QUOTE = {"NIFTY": "NSE:NIFTY 50", "SENSEX": "BSE:SENSEX"}
STEP = {"NIFTY": 50, "SENSEX": 100}
LOCK = threading.RLock()
STOP = threading.Event()
instrument_cache: dict[str, tuple[date, list[dict]]] = {}
baseline_cache: dict[tuple, tuple[float, float]] = {}

app = Flask(__name__)
TOKEN_MANAGER = TokenManager(CREDENTIALS_PATH, DB_PATH)


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY CHECK(id=1), instrument TEXT NOT NULL,
          expiry_rank INTEGER NOT NULL, strike_count INTEGER NOT NULL,
          interval_minutes INTEGER NOT NULL, updated_at TEXT NOT NULL,
          zerodha_id TEXT NOT NULL DEFAULT '',
          full_day_strike_count INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS token_sessions (
          zerodha_id TEXT PRIMARY KEY, access_token TEXT NOT NULL,
          generated_at TEXT NOT NULL, validated_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS snapshots (
          id INTEGER PRIMARY KEY AUTOINCREMENT, trade_date TEXT NOT NULL,
          captured_at TEXT NOT NULL, instrument TEXT NOT NULL, expiry TEXT NOT NULL,
          atm INTEGER NOT NULL, strike_count INTEGER NOT NULL,
          call_oi REAL NOT NULL, put_oi REAL NOT NULL,
          prev_call_oi REAL NOT NULL, prev_put_oi REAL NOT NULL,
          full_call_oi REAL, full_put_oi REAL,
          full_prev_call_oi REAL, full_prev_put_oi REAL,
          full_day_scope TEXT,
          UNIQUE(instrument, captured_at));
        """)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(settings)")}
        if "zerodha_id" not in columns:
            conn.execute("ALTER TABLE settings ADD COLUMN zerodha_id TEXT NOT NULL DEFAULT ''")
        if "full_day_strike_count" not in columns:
            conn.execute("ALTER TABLE settings ADD COLUMN full_day_strike_count INTEGER NOT NULL DEFAULT 0")
        snapshot_columns = {row[1] for row in conn.execute("PRAGMA table_info(snapshots)")}
        for name, column_type in (("full_call_oi", "REAL"), ("full_put_oi", "REAL"), ("full_prev_call_oi", "REAL"), ("full_prev_put_oi", "REAL"), ("full_day_scope", "TEXT")):
            if name not in snapshot_columns:
                conn.execute(f"ALTER TABLE snapshots ADD COLUMN {name} {column_type}")
        conn.execute("""INSERT OR IGNORE INTO settings
          (id,instrument,expiry_rank,strike_count,interval_minutes,updated_at,zerodha_id,full_day_strike_count)
          VALUES (1,'NIFTY',0,5,1,CURRENT_TIMESTAMP,'',0)""")
        conn.execute("UPDATE settings SET interval_minutes=1 WHERE id=1")


def kite() -> KiteConnect:
    zerodha_id = settings().get("zerodha_id", "").strip()
    if not zerodha_id:
        raise RuntimeError("Select and save a Zerodha ID on the dashboard first")
    return TOKEN_MANAGER.client(zerodha_id)


def settings() -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM settings WHERE id=1").fetchone()
    return dict(row)


def instruments(client: KiteConnect, exchange: str) -> list[dict]:
    cached = instrument_cache.get(exchange)
    if cached and cached[0] == date.today():
        return cached[1]
    data = client.instruments(exchange)
    instrument_cache[exchange] = (date.today(), data)
    return data


def option_set(client: KiteConnect, name: str, expiry_rank: int, count: int):
    exchange = EXCHANGE[name]
    all_rows = instruments(client, exchange)
    index_ltp = float(client.ltp(INDEX_QUOTE[name])[INDEX_QUOTE[name]]["last_price"])
    atm = round(index_ltp / STEP[name]) * STEP[name]
    today = date.today()
    rows = [r for r in all_rows if str(r.get("name", "")).upper() == name and r.get("instrument_type") in ("CE", "PE") and r.get("expiry") and r["expiry"] >= today]
    expiries = sorted({r["expiry"] for r in rows})
    if not expiries:
        raise RuntimeError(f"No active {name} option expiry found in {exchange}")
    expiry = expiries[min(expiry_rank, len(expiries) - 1)]
    expiry_rows = [r for r in rows if r["expiry"] == expiry]
    if count == 0:
        calls = [r for r in expiry_rows if r["instrument_type"] == "CE"]
        puts = [r for r in expiry_rows if r["instrument_type"] == "PE"]
        if not calls or not puts:
            raise RuntimeError(f"No CE/PE strikes found for {name} {expiry}")
        return exchange, expiry, int(atm), calls, puts
    ce_strikes = {atm + STEP[name] * i for i in range(count)}
    pe_strikes = {atm - STEP[name] * i for i in range(count)}
    selected = [r for r in expiry_rows if (r["instrument_type"] == "CE" and int(r["strike"]) in ce_strikes) or (r["instrument_type"] == "PE" and int(r["strike"]) in pe_strikes)]
    calls = [r for r in selected if r["instrument_type"] == "CE"]
    puts = [r for r in selected if r["instrument_type"] == "PE"]
    if len(calls) != count or len(puts) != count:
        raise RuntimeError(f"Expected {count} CE and PE strikes; found {len(calls)} CE and {len(puts)} PE")
    return exchange, expiry, int(atm), calls, puts


def previous_close_oi(client: KiteConnect, expiry, calls, puts):
    key = (str(expiry), tuple(r["instrument_token"] for r in calls + puts))
    if key in baseline_cache:
        return baseline_cache[key]
    end = datetime.now()
    start = end - timedelta(days=8)
    result = {"CE": 0, "PE": 0}
    for row in calls + puts:
        candles = client.historical_data(row["instrument_token"], start, end, "day", oi=True)
        completed = [c for c in candles if c["date"].date() < date.today()]
        if completed:
            result[row["instrument_type"]] += float(completed[-1].get("oi", 0))
        time.sleep(0.35)
    answer = result["CE"] / 100000, result["PE"] / 100000
    baseline_cache[key] = answer
    return answer


def quote_many(client: KiteConnect, symbols: list[str]) -> dict:
    result = {}
    unique_symbols = list(dict.fromkeys(symbols))
    for index in range(0, len(unique_symbols), 400):
        result.update(client.quote(unique_symbols[index:index + 400]))
    return result


def capture(force=False) -> dict:
    cfg = settings()
    now = datetime.now()
    with LOCK:
        if not force:
            with db() as conn:
                last = conn.execute("SELECT captured_at FROM snapshots WHERE instrument=? AND trade_date=? ORDER BY id DESC LIMIT 1", (cfg["instrument"], now.date().isoformat())).fetchone()
            if last and (now - datetime.fromisoformat(last["captured_at"])).total_seconds() < cfg["interval_minutes"] * 60 - 2:
                return {"skipped": True}
        client = kite()
        exchange, expiry, atm, calls, puts = option_set(client, cfg["instrument"], cfg["expiry_rank"], cfg["strike_count"])
        _, full_expiry, _, full_calls, full_puts = option_set(client, cfg["instrument"], cfg["expiry_rank"], cfg["full_day_strike_count"])
        symbols = [f"{exchange}:{r['tradingsymbol']}" for r in calls + puts + full_calls + full_puts]
        quotes = quote_many(client, symbols)
        call_oi = sum(float(quotes.get(f"{exchange}:{r['tradingsymbol']}", {}).get("oi", 0)) for r in calls) / 100000
        put_oi = sum(float(quotes.get(f"{exchange}:{r['tradingsymbol']}", {}).get("oi", 0)) for r in puts) / 100000
        full_call_oi = sum(float(quotes.get(f"{exchange}:{r['tradingsymbol']}", {}).get("oi", 0)) for r in full_calls) / 100000
        full_put_oi = sum(float(quotes.get(f"{exchange}:{r['tradingsymbol']}", {}).get("oi", 0)) for r in full_puts) / 100000
        prev_call, prev_put = previous_close_oi(client, expiry, calls, puts)
        if {r["instrument_token"] for r in calls + puts} == {r["instrument_token"] for r in full_calls + full_puts}:
            full_prev_call, full_prev_put = prev_call, prev_put
        else:
            full_prev_call, full_prev_put = previous_close_oi(client, full_expiry, full_calls, full_puts)
        full_scope = "ALL" if cfg["full_day_strike_count"] == 0 else f"ATM+{cfg['full_day_strike_count'] - 1}OTM"
        stamp = now.replace(microsecond=0).isoformat()
        with db() as conn:
            conn.execute("""INSERT OR REPLACE INTO snapshots
              (trade_date,captured_at,instrument,expiry,atm,strike_count,call_oi,put_oi,prev_call_oi,prev_put_oi,
               full_call_oi,full_put_oi,full_prev_call_oi,full_prev_put_oi,full_day_scope)
              VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (now.date().isoformat(), stamp, cfg["instrument"], str(expiry), atm, cfg["strike_count"], call_oi, put_oi, prev_call, prev_put, full_call_oi, full_put_oi, full_prev_call, full_prev_put, full_scope))
        return {"captured_at": stamp, "call_oi": call_oi, "put_oi": put_oi, "full_call_oi": full_call_oi, "full_put_oi": full_put_oi, "atm": atm, "expiry": str(expiry), "full_day_scope": full_scope}


def dashboard_data() -> dict:
    cfg = settings()
    with db() as conn:
        raw = conn.execute("SELECT * FROM snapshots WHERE instrument=? AND trade_date=? ORDER BY captured_at", (cfg["instrument"], date.today().isoformat())).fetchall()
    result, previous_row = [], None
    for item in raw:
        row = dict(item)
        row["time"] = datetime.fromisoformat(row["captured_at"]).strftime("%H:%M")
        row["ce_diff"] = None if previous_row is None else row["call_oi"] - previous_row["call_oi"]
        row["pe_diff"] = None if previous_row is None else row["put_oi"] - previous_row["put_oi"]
        expected_scope = "ALL" if cfg["full_day_strike_count"] == 0 else f"ATM+{cfg['full_day_strike_count'] - 1}OTM"
        if row.get("full_day_scope") == expected_scope and row.get("full_call_oi") is not None:
            row["ce_day"] = row["full_call_oi"] - row["full_prev_call_oi"]
            row["pe_day"] = row["full_put_oi"] - row["full_prev_put_oi"]
        else:
            row["ce_day"] = None
            row["pe_day"] = None
        row["pcr"] = row["put_oi"] / row["call_oi"] if row["call_oi"] else None
        result.append(row)
        previous_row = row
    summary = None
    if result:
        summary = {"ce_first_to_latest": result[-1]["call_oi"] - result[0]["call_oi"], "pe_first_to_latest": result[-1]["put_oi"] - result[0]["put_oi"], "latest": result[-1]}
    return {"settings": cfg, "rows": result, "summary": summary, "credential_file": str(CREDENTIALS_PATH), "accounts": TOKEN_MANAGER.accounts()}


def worker() -> None:
    while not STOP.wait(10):
        now = datetime.now()
        if now.weekday() < 5 and dt_time(9, 15) <= now.time() <= dt_time(15, 40):
            try:
                capture(False)
            except Exception as exc:
                app.logger.warning("Scheduled capture failed: %s", exc)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/data")
def api_data():
    try:
        return jsonify({"ok": True, **dashboard_data()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/settings")
def api_settings():
    payload = request.get_json(force=True)
    instrument = str(payload.get("instrument", "NIFTY")).upper()
    interval = 1
    strike_count = max(1, min(20, int(payload.get("strike_count", 5))))
    full_day_strike_count = int(payload.get("full_day_strike_count", 0))
    if full_day_strike_count not in (0, 3, 5, 7, 11):
        full_day_strike_count = 0
    expiry_rank = max(0, min(5, int(payload.get("expiry_rank", 0))))
    zerodha_id = str(payload.get("zerodha_id", "")).strip().upper()
    if instrument not in EXCHANGE:
        return jsonify({"ok": False, "error": "Instrument must be NIFTY or SENSEX"}), 400
    with db() as conn:
        conn.execute("UPDATE settings SET instrument=?,expiry_rank=?,strike_count=?,interval_minutes=?,zerodha_id=?,full_day_strike_count=?,updated_at=? WHERE id=1", (instrument, expiry_rank, strike_count, interval, zerodha_id, full_day_strike_count, datetime.now().isoformat()))
    return jsonify({"ok": True, "settings": settings()})


@app.post("/api/capture")
def api_capture():
    try:
        return jsonify({"ok": True, "result": capture(True)})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/clear-today")
def api_clear_today():
    cfg = settings()
    with db() as conn:
        conn.execute("DELETE FROM snapshots WHERE instrument=? AND trade_date=?", (cfg["instrument"], date.today().isoformat()))
    return jsonify({"ok": True})


@app.post("/api/regenerate-token")
def api_regenerate_token():
    try:
        zerodha_id = settings().get("zerodha_id", "").strip()
        if not zerodha_id:
            raise RuntimeError("Save a Zerodha ID first")
        TOKEN_MANAGER.client(zerodha_id, force_new=True)
        return jsonify({"ok": True})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.post("/api/credentials")
def api_credentials():
    try:
        payload = request.get_json(force=True)
        account_id = str(payload.get("zerodha_id", "")).strip().upper()
        required = ("api_key", "api_secret", "username", "password", "totp_secret")
        entry = {key: str(payload.get(key, "")).strip() for key in required}
        if not account_id:
            return jsonify({"ok": False, "error": "Zerodha ID is required."}), 400
        missing = [key for key in required if not entry[key]]
        if missing:
            return jsonify({"ok": False, "error": "All fields are required: " + ", ".join(missing)}), 400
        data = {}
        if CREDENTIALS_PATH.exists():
            try:
                loaded = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data[account_id] = entry
        CREDENTIALS_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return jsonify({"ok": True, "accounts": TOKEN_MANAGER.accounts()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    init_db()
    thread = threading.Thread(target=worker, name="oi-sampler", daemon=True)
    thread.start()
    atexit.register(STOP.set)
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
