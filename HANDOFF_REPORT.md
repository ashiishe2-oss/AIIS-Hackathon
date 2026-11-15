# AIIS frontend handoff report (14 Nov 2026)

## 1. Technology stack

- **Frontend:** vanilla HTML5, CSS and JavaScript (ES2020, one IIFE). Hash router, no framework, no TypeScript, no build step, no npm runtime dependencies.
- **Vendored library:** qrcode-generator (MIT).
- **Fonts:** the device's system font.
- **PWA:** manifest and icons (no service worker).
- **Not Flask/Jinja:** the frontend is static files. It was served by a Node backend (V1) and deployed on Vercel.
- **Handoff tooling added:** `dev-server.js`, a zero-dependency Node 18+ static server with an `/api` proxy.

## 2. Folder structure

```
public/  (index.html, app.js, styles.css, manifest.json, icon.svg, icon-512.png, vendor/qrcode.js + licence)
dev-server.js · package.json · .env.example
README.md · FRONTEND_API_INVENTORY.md · FRONTEND_INTEGRATION_NOTES.md · HANDOFF_REPORT.md
reference/v1-sample-responses/  (19 JSON samples + README)
```

## 3. Files included

- **Frontend source and assets (`public/`):** 8 files.
  - Source: 3 files (`index.html`, `app.js` with 1,400 lines, `styles.css`).
  - Assets: 3 files (two icons and the manifest).
  - Vendor: 2 files (library and licence).
- **Whole package:** 35 files.
- **`public/` is byte-identical** to the repository's v1.2 frontend (commit `cc30cd4`). No UI file was changed.

## 4. Startup command

```bash
npm start                                      # http://localhost:8080, frontend only
AIIS_API_BASE=http://localhost:5000 npm start   # with Backend V2
```

## 5. API endpoint inventory summary

There are 13 endpoints, all relative `/api/...`, using only GET and POST. Details are in `FRONTEND_API_INVENTORY.md`.

| # | Method | Path | Feature | Auth |
|---|---|---|---|---|
| 1 | POST | `/api/emergency/search` | Emergency hospital search | Public |
| 2 | GET | `/api/locations` | Area list | Public |
| 3 | GET | `/api/hospitals/:id` | Hospital details | Public |
| 4 | POST | `/api/planned/search` | Planned-care search | Public |
| 5 | POST | `/api/coordination/request` | Pre-arrival bed hold (partner hospitals only) | Public |
| 6 | GET | `/api/coordination/:id` | Request tracking (polled every 3 s) | Public |
| 7 | POST | `/api/coordination/:id/cancel` | Cancel request | Public |
| 8 | POST | `/api/coordination/:id/verify-arrival` | Arrival code check | Public (no staff auth) |
| 9 | POST | `/api/appointments/request` | Visit request (partner hospitals only) | Public |
| 10 | GET | `/api/appointments?phone=` | My visit requests | Public, by phone number |
| 11 | POST | `/api/appointments/:id/cancel` | Cancel visit | Public |
| 12 | POST | `/api/hospitals/:id/capacity` | Staff bed update | `X-AIIS-Staff-Code` header |
| 13 | GET | `/api/sri/regional` | Strain Risk Index | Public |

**Not in the frontend:** registration, login, JWT or guest tokens, the authority dashboard, and SOS dispatch.

## 6. Authentication and token handling

There are no user accounts and nothing token-like is stored.

- **Staff screen:** sends a shared access code in `X-AIIS-Staff-Code`. It is kept in memory only.
- **`localStorage`:** holds only location, the active request id, visit-request copies and an optional saved name and phone (keys `aiis.*`).

## 7. Hardcoded API URLs needing integration changes

- **`public/`:** none. All calls are relative `/api/...` and there is no `localhost`.
  - Integrate by serving the frontend and Backend V2 from **one origin**: the included proxy, or Flask serving `public/`.
  - Alternatively, add a base URL to `api()` and configure CORS.
  - Assets use root paths, so host the app at a domain root.
- **Outside this package:** the Android app hard-codes `https://aiis-livid.vercel.app` (`App.BASE_URL`).

## 8. Mock or static data still present

These all come from the V1 backend, not from the frontend:

| Data | Status |
|---|---|
| Hospital list | Real hospitals and checked numbers, but static |
| Bed counts | Null until staff publish them |
| Bed-hold acceptance | Simulated by a timer, and only for partner hospitals, of which there are none |
| Visit-request store | In memory |
| SRI values | Sample |
| Area list | Fixed |

- **In the frontend:** the constant `PHONES_CHECKED = '2026-11-13'` (footer text) and a "Demo data" badge that appears if the backend sends `isSimulated: true`.
- **Not converted into live claims:** the UI shows "call to check" when no beds are published.

## 9. Known limitations

1. There are no auth screens and no authority dashboard.
2. Every error box is titled "Could not load hospitals".
3. Request tracking keeps polling on non-404 errors.
4. The appointment list is retrieved by phone number with no verification.
5. Arrival verification has no staff authentication.
6. Unknown routes fall back to Home.
7. The app must be hosted at a domain root.

## 10. Secrets check

**No secrets are included.**

- The package was scanned for API keys, JWTs, service-role keys, private keys, passwords and `.env` files. None were found.
- `.env.example` holds placeholders only (`PORT`, `AIIS_API_BASE`).
- The Android signing key, `.git`, `node_modules`, logs, build output and the backend are not included.
- The only credential-like input is the staff code typed at runtime, which is never stored or bundled.

## 11. Testing done

- Syntax checks: pass.
- **Frontend alone:** all 6 screens render, and API calls fail with a clear 503 message. No JavaScript exceptions.
- **Through the proxy against the current V1 backend:**
  - search, details, planned care (15 results), SRI and staff publish work;
  - unknown request ids get a 404 and show "Request not found".
- **Not tested against Backend V2.** It was not available here, so integration is **not** confirmed.

## 12. ZIP

`AIIS_FRONTEND_HANDOFF.zip`, with the top-level folder `AIIS_FRONTEND_HANDOFF/`. It was extracted and re-tested after packing.
