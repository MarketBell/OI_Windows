# OI Pulse Dashboard

A real-time **Open Interest (OI) analytics dashboard** for **NIFTY** and **SENSEX**, by
**Billionit Wealth**. It runs entirely on your **own Windows PC** using **your own Zerodha
account** — your login details never leave your computer.

- Live intraday + full-day OI change, PCR, ATM/OTM strike analysis
- Automatic minute-by-minute capture during market hours
- All data stays local on your machine

---

## What you need

- A **Windows 10/11 PC**.
- **Google Chrome** installed.
- A **Zerodha** trading account with **Kite Connect API access** (see *Linking your Zerodha API
  account* below — this is a Zerodha developer subscription).
- Your **OI Pulse license key** (sent to you after purchase).

---

## 1. Install

1. Double-click the installer you received: **`OI-Pulse-Dashboard-Setup.exe`**.
2. Click through **Next → Install → Finish**. (It installs just for you — no admin password
   needed, and no Windows settings are changed.)
3. Launch **OI Pulse Dashboard** from the desktop or Start menu.

A small black status window opens and your browser opens the dashboard at
`http://127.0.0.1:5069`. Keep the black window open while you use the app — closing it stops the
app.

---

## 2. First-run setup (one time)

The first time you open the app, a **"Set up OI Pulse"** form appears. Fill in:

| Field | Where it comes from |
|-------|---------------------|
| **License key** | The key emailed to you after purchase (e.g. `OIPD-XXXX-XXXX-XXXX`). |
| **Zerodha ID** | Your Zerodha client/user ID (e.g. `AB1234`). |
| **API key** | From your Kite Connect app (see below). |
| **API secret** | From your Kite Connect app (see below). |
| **Username** | Your Zerodha login ID (same as Zerodha ID). |
| **Password** | Your Zerodha login password. |
| **TOTP secret** | Your Zerodha external 2FA (TOTP) secret (see below). |

Click **Save**. Everything is stored **only on your PC**. That's it — you won't need to enter this
again unless you change a password or move to a new PC.

> **Your license** is tied to **your Zerodha account**. You can install and use it on **as many of
> your own PCs as you like** with the same license — but it will not work on someone else's Zerodha
> login.

---

## 3. Linking your Zerodha API account

The app logs into Zerodha for you using the **Kite Connect API**. You supply four things once:
**API key**, **API secret**, and your **login password** + **TOTP secret**.

### a) Get your API key & API secret (Kite Connect)

1. Go to **https://developers.kite.trade/** and log in with your Zerodha account.
2. Open **My apps → Create new app** (this is Zerodha's **Kite Connect** developer subscription;
   a monthly fee applies as per Zerodha's current pricing).
3. Fill in:
   - **App name:** anything (e.g. *OI Pulse*).
   - **Redirect URL:** `http://127.0.0.1:5069`
   - **Postback URL:** leave blank.
4. Create the app. Open it and copy the **API key** and **API secret** — paste these into the
   first-run form.

### b) Get your TOTP secret (external 2FA)

The app needs an app-based **TOTP** 2FA (not SMS OTP) so it can log in automatically.

1. In **Kite** (web) → **Profile → Settings → Account security → External 2FA / TOTP** →
   **Enable / set up TOTP**.
2. Zerodha shows a QR code **and** a text **secret key** (a string of letters/numbers). **Copy that
   secret key** — that is your **TOTP secret** for the form.
3. Finish Zerodha's TOTP setup (scan the QR in Google Authenticator too, so you always have a
   backup code).

> Keep the TOTP secret private — it, your password and API secret together are what let the app log
> in. They are saved only on your own PC.

---

## 4. Using the dashboard

1. Select your **Zerodha ID** and click **Save settings** (it stays selected next time).
2. Click **Capture now** — the app validates or generates a login token automatically and pulls
   live OI.
3. The dashboard auto-captures every minute, **Mon–Fri, 09:15–15:30**.
4. Use **New token** only if you're asked to re-login.

Set `OI_PULSE_SHOW_LOGIN=1` before launching if you want to watch the Chrome login happen;
otherwise it runs invisibly.

---

## How it works (reference)

### Token workflow
- The selected Zerodha ID is saved locally in `oi_pulse.db`.
- On the first request after startup, the saved token is checked via the Kite profile API. If
  valid, it is reused; if missing/invalid, Chrome login + password + TOTP run automatically and the
  new access token is saved locally.
- **New token** forces regeneration when required.

### Strike logic
- CE: ATM and higher OTM strikes; PE: ATM and lower OTM strikes (for both NIFTY and SENSEX).
- The chosen strike count applies separately to CE and PE — e.g. *ATM + 4 OTM* sums five CE and
  five PE strikes.

### Calculations
- **Intraday change** = current saved OI − immediately preceding saved OI.
- **Full-day change** = live OI − previous trading day's closing OI.
- The full-day table has its own strike selector (default **All Strikes** for the expiry).
- **Bottom total** = latest saved OI − first saved OI of the day.
- **PCR** = combined Put OI ÷ combined Call OI.
- OI values are shown in lakhs. The first All-Strikes capture can take longer (it caches every
  contract's previous close).

### Notes
- Chrome must be installed; Selenium Manager fetches a compatible driver automatically.
- All snapshots and settings stay in `oi_pulse.db` on your PC.
- This is an **analysis tool** — it does **not** place orders and is **not** investment advice.

---

## Support

Questions or a new license? Contact **Billionit Wealth** — **billionitwealth@gmail.com** ·
**https://billionitwealth.in**

_A step-by-step install & API-linking guide is also provided as a **PDF** (`docs/OI_Pulse_Install_Guide.pdf`)._
