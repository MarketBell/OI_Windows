# Building & packaging — OI Pulse Dashboard

This turns the Python app into a Windows installer buyers can double-click. Nothing here changes
the app's source; it only packages it.

**Pipeline:** PyInstaller (make the `.exe`) → Inno Setup (make the installer). Optionally add
PyArmor first to obfuscate the code + license check.

All commands are run from the **project root** (`OI_Windows\`), not from `packaging\`.

---

## 0. Prerequisites (one-time, on a dev PC)

- **Python 3.11+** (64-bit) with `py` on PATH.
- **Google Chrome** installed (the app uses Selenium; Selenium Manager fetches the driver at run
  time — so the build PC and every buyer PC need Chrome).
- **Inno Setup 6** — https://jrsoftware.org/isdl.php (gives you the Inno Setup Compiler + `ISCC.exe`).
- Project deps install automatically during the build from `requirements.txt`.

---

## 1. Plain build (do this first — proves the exe works)

```bat
packaging\build.bat
```

This installs PyInstaller, cleans old output, and builds using `packaging\oi_pulse.spec`.

Output: **`dist\OI Pulse Dashboard\`** (a folder — the `.exe` plus its `_internal` support files).

**Test it right away:**

```bat
"dist\OI Pulse Dashboard\OI Pulse Dashboard.exe"
```

A console window opens, the local server starts on `127.0.0.1:5069`, and your browser opens the
dashboard. First run shows the **"Set up OI Pulse"** form (license key + Zerodha API details).
Close the console window to stop the app.

> The app writes `oi_pulse.db`, `zerodha_credentials.json` and `license.json` **next to itself**.
> That's why the installer (step 3) installs per-user into a writable folder — see the note there.

---

## 2. Make the installer (Inno Setup)

Either open `packaging\installer.iss` in the **Inno Setup Compiler** and press **Build**, or:

```bat
ISCC.exe packaging\installer.iss
```

Output: **`packaging\Output\OI-Pulse-Dashboard-Setup-1.0.0.exe`** — this single file is what you
give buyers.

The installer:
- installs **per-user** into `%LOCALAPPDATA%\OI Pulse Dashboard` (no admin prompt, and the folder
  is **writable** so the app's data/license files save correctly — installing into Program Files
  would break those writes),
- creates Start-menu (and optional desktop) shortcuts,
- offers to launch the app at the end.

Bump `AppVersion` in `installer.iss` for each new release.

---

## 3. Hardened build (PyArmor — optional but recommended before selling)

Obfuscates `app.py`, `token_manager.py`, `license_manager.py` so the license check can't be
trivially removed, then packs the exe.

**Option 2a — one shot (try this first):**

```bat
packaging\build_protected.bat
```

It runs `pyarmor gen --pack packaging\oi_pulse.spec app.py token_manager.py license_manager.py`.

**Option 2b — manual two-step (fallback if `--pack` errors on your PyArmor version):**

```bat
py -m pip install --upgrade pyarmor pyinstaller
pyarmor gen -O obfdist --recursive app.py token_manager.py license_manager.py
REM  then build from the obfuscated copy: copy templates/static + the pyarmor_runtime
REM  package next to obfdist\app.py and run PyInstaller on obfdist\app.py, reusing the
REM  hidden-imports/datas from oi_pulse.spec.
```

PyArmor's CLI differs a little between versions — check `pyarmor --version` and its docs
(https://pyarmor.readthedocs.io) if a flag is rejected. Always **re-test the hardened exe** (the
whole login → dashboard → license flow) because obfuscation occasionally trips a dynamic import.

After a successful hardened build, make the installer exactly as in step 2.

---

## 4. Ship checklist

1. `packaging\build.bat` → test the exe.  (or `build_protected.bat` for the hardened one)
2. `ISCC.exe packaging\installer.iss` → get the setup `.exe`.
3. **Test the setup on a clean Windows PC** (no Python installed) — only Chrome present. Install,
   launch, enter a real license key + Zerodha details, confirm the dashboard loads live data.
4. Confirm licensing end-to-end: a valid key binds to the buyer's Zerodha account; the same key on
   a second PC (same account) works; a different Zerodha account is rejected.
5. (Optional) **Code-sign** the setup `.exe` with an OV/EV certificate to avoid the Windows
   SmartScreen "unknown publisher" warning.
6. Deliver the setup `.exe` + the license key to the buyer (see the top-level README for the
   buyer-facing install & API-linking guide).

---

## Notes / gotchas

- **Chrome is required on the buyer's PC.** If a buyer has no Chrome, login fails. State this in the
  purchase page / README.
- **License server:** the exe calls `https://license.billionitwealth.in` to activate. For a build-
  time smoke test without a key you can set `OI_PULSE_LICENSE_DISABLE=1` in the environment — never
  ship with that set.
- **onedir, not onefile:** onefile unpacks to a temp dir each launch and hides the data files from
  the user; onedir keeps `oi_pulse.db` / `license.json` visible and stable. Keep onedir.
- **Antivirus / SmartScreen:** unsigned PyInstaller exes sometimes get flagged. Code-signing (step
  5) fixes the publisher warning; for false-positive AV flags, submit the exe to the vendor or sign.
- **Rebuilds:** both build scripts delete `build\` and `dist\` first, so each run is clean.
