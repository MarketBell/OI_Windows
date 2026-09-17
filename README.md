# OI Pulse Dashboard

Local Zerodha Kite open-interest dashboard for NIFTY and SENSEX.

## Install and run on Windows

1. Extract the ZIP to `D:\Python-Scripts\OI_Pulse_Dashboard`.
2. Rename `zerodha_credentials.example.json` to `zerodha_credentials.json`.
3. Add every Zerodha account using the same structure shown in the example. Do not add an access token.
4. Double-click `run_dashboard.bat`.
5. Select the Zerodha ID on the web page and click **Save settings**. The selected ID remains saved until you change it.
6. Click **Capture now**. The program validates a stored token or generates a new one automatically.
7. The browser opens at `http://127.0.0.1:5069`.

To use another credentials-file location, set `OI_PULSE_CREDENTIALS` to its full path before launching.

## Token workflow

- No token is read from `C:\Token\config.json`.
- The selected Zerodha ID is saved in `oi_pulse.db`.
- During the first request after startup, the saved token is checked using the Kite profile API.
- If valid, token generation is skipped and the same token is reused in memory.
- If missing or invalid, Chrome login, password and TOTP entry run automatically; the returned request token is exchanged using `api_secret` and the new access token is saved in the local database.
- On a second program start, the database token is checked first. A new token is generated only when validation fails.
- **New token** forces regeneration when required.
- Set `OI_PULSE_SHOW_LOGIN=1` if you want to see the Chrome login window; otherwise it runs headlessly.

## Strike logic

- NIFTY CE: ATM and higher OTM strikes; PE: ATM and lower OTM strikes.
- SENSEX CE: ATM and higher OTM strikes; PE: ATM and lower OTM strikes.
- The chosen strike count applies separately to CE and PE. For `ATM + 4 OTM`, five CE and five PE strikes are summed.

## Calculations

- Intraday DF = current saved OI minus immediately preceding saved OI.
- Full-day OI change = live OI minus the previous trading day's closing OI.
- The full-day table has an independent strike selector. Its default is **All Strikes** for the selected expiry; optional ATM + OTM ranges are also available.
- Intraday and full-day strike selections are calculated and stored independently.
- The first All-Strikes capture can take longer because previous-close OI is fetched and cached for every CE/PE contract in the expiry.
- Bottom total = latest saved OI minus first saved OI of the day.
- PCR = combined Put OI divided by combined Call OI.
- OI values are displayed in lakhs.

## Notes

- Chrome must be installed. Selenium Manager obtains a compatible driver automatically when permitted by your network.
- Keep `zerodha_credentials.json` private; it contains login and TOTP secrets.
- Snapshots are stored locally in `oi_pulse.db`.
- Automatic capture runs Monday–Friday between 09:15 and 15:30.
- Raw OI is collected every minute. Start Time, End Time and Data Frequency only control which readings are displayed and exported.
- Both data tables stay at a fixed height and scroll internally, so one-minute readings do not make the page longer.
- Use **Capture now** to save an immediate reading.
- This is an analysis tool, not an order-placement system.
