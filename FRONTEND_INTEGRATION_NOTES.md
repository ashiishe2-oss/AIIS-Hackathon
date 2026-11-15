# AIIS frontend: integration notes for Backend V2 (Flask + Supabase)

**Status: not integrated.** This frontend has been tested on its own (with no backend) and through the included dev proxy against the **current V1 Node backend**. It has **not** been run against Backend V2.

## 1. API base URL

- **No base URL exists in the code.** Every call is a relative path: `fetch('/api/...')` in `public/app.js` → `api()`.
- **No hardcoded `localhost` or absolute API URL** appears anywhere in `public/`.
- The page loads its assets from root-absolute paths (`/styles.css`, `/app.js`, `/vendor/qrcode.js`, `/manifest.json`, `/icon.svg`). **It must be served from a domain root**, not from a sub-path like `/app/`.
- **Absolute URLs that do exist** (all external and intentional):
  - `https://www.google.com/maps/dir/?api=1&destination=lat,lng` and `https://www.google.com/maps/search/?api=1&query=…` (Directions links; no API key)
  - `https://wa.me/?text=…` (Send to family)
  - `tel:` links, including `tel:108` and `tel:112`
- **Android app (separate client, not in this package):** `App.BASE_URL = "https://aiis-livid.vercel.app"` is hard-coded. Pointing Android at Backend V2 needs a rebuild.

### Three ways to connect Backend V2 (pick one; no frontend code change is needed for any of them)

| Option | How | CORS |
|---|---|---|
| A. Dev proxy (included) | Run `AIIS_API_BASE=http://localhost:5000 npm start`. `dev-server.js` serves `public/` on :8080 and forwards `/api/*` to Flask, passing on the `Content-Type`, `Authorization`, `X-AIIS-Staff-Code` and `Accept` headers. | Not needed (same origin) |
| B. Flask serves the files | Copy `public/` into Flask's static folder. Serve `index.html` at `/` and the other files at their root paths, e.g. `Flask(__name__, static_folder='public', static_url_path='')`. | Not needed |
| C. Separate origins | Add an API base to `api()` in `app.js` (a one-line change, **not made in this package**). | Flask must allow the frontend origin, methods `GET, POST, OPTIONS` and headers `Content-Type, X-AIIS-Staff-Code` (plus `Authorization` if JWT is added later). |

The current V1 backend sends `Access-Control-Allow-Origin: *`. The frontend does not depend on that when it is served same-origin.

## 2. Expected backend port and URL

There is none in the frontend; whatever origin serves the page is used. For local work, the dev proxy expects `AIIS_API_BASE` (example: `http://localhost:5000`, Flask's default). In production today, `https://aiis-livid.vercel.app/api/*` is served by the V1 Node function.

## 3. Authentication and tokens

- **No user accounts.** There is no login or registration screen, no JWT and no guest token. Nothing token-like is stored.
- **Staff bed updates** send `X-AIIS-Staff-Code: <code>` typed on `#/hospital`. It is held in memory only and never saved. Backend V2 must accept this header or the screen must be changed to JWT (a frontend change).
- **Arrival verification** (`/verify-arrival`) is called without any staff credential.

## 4. What the frontend stores in `localStorage` (keys prefixed `aiis.`)

| Key | Content |
|---|---|
| `aiis.loc` | Last chosen location `{name, lat, lng, source}` |
| `aiis.coord` | Active pre-arrival request id |
| `aiis.appts` | Copies of visit requests (hospital, date, slot, status, patient phone) |
| `aiis.profile` | Patient name and phone, only if "Remember" is ticked; removable from "My requests" |
| `aiis.staffHospital` | Last hospital chosen on the staff screen |

Every access is wrapped in try/catch, so the app works when storage is blocked.

## 5. Environment variables

The **browser app reads none.** Only `dev-server.js` uses environment variables: `PORT` (default 8080) and `AIIS_API_BASE`. See `.env.example`.

**Never put the Supabase service-role key, database URL, JWT secret or `AIIS_STAFF_CODE` in the frontend.** They belong in Backend V2's environment only.

If the frontend later talks to Supabase directly (it does not today), only the project URL and the public anon/publishable key may be exposed, with Row Level Security on.

## 6. Permissions and browser features

| Feature | Use |
|---|---|
| Geolocation | `navigator.geolocation.getCurrentPosition` with `enableHighAccuracy: true`, an 8 s timeout and a 5 min maximum age. It is requested automatically on `#/emergency`. If it is refused, the app falls back to a chosen area (default: Bengaluru Central). Needs **HTTPS** (or localhost). |
| `navigator.share` | Send to family (WhatsApp link fallback) |
| `navigator.vibrate` | On "hospital accepted" |
| `window.AIISNative` | Bridge present only inside the Android app (share, shake settings). Optional. |

## 7. External dependencies

- `public/vendor/qrcode.js`: qrcode-generator by Kazuhiko Arase (MIT, vendored; licence included).
- Fonts: the phone's system font. There are no web-font requests.
- There is no CDN, analytics, map SDK, build step, framework or npm runtime dependency.

## 8. Data shown and where it comes from (live vs static)

| Data | Source today | Live? |
|---|---|---|
| Hospital list (22 Bengaluru hospitals), addresses, phone numbers | Backend V1 `data/hospitals.js`: real hospitals, numbers checked 13 Nov 2026. 17 numbers come from hospital websites and 5 government numbers from public lists (flagged in the UI). | Static reference data, **not a live feed** |
| Bed counts | `null` until staff publish them with the access code. The UI shows "call to check". | Live only after a staff update (in memory on V1) |
| Travel time / distance | Backend estimate from straight-line distance | Estimate, not live traffic |
| Pre-arrival bed hold status | V1 store **simulates** hospital acceptance on a timer. Reachable only for `partner: true` hospitals, of which there are none. | **Demo only** |
| Visit requests | V1 in-memory store; reachable only for partner hospitals (none) | **Demo only** |
| Strain Risk Index | V1 `data/regional_sri.js`, sample values | **Sample data, not a trained model** |
| Area list | V1 `REGIONAL_CENTERS` (fixed list) | Static |
| Client constant | `PHONES_CHECKED = '2026-11-13'` in `app.js` (footer text) | Static |
| "Demo data" badge | Shown when a response has `dataFreshness.isSimulated: true` or a `source` containing "demo" | Driven by the backend |

## 9. Features not connected to any real backend workflow

- "Tell them I'm coming" and the request tracking, cancel and verify-arrival screens: hidden unless `partner: true`.
- "Request visit" and the appointment list/cancel: hidden unless `partner: true`.
- Staff screen: works against V1, but without accounts, and data is lost on restart.
- SRI page: shows sample data.
- Login, registration, authority dashboard and SOS dispatch: **do not exist** in this frontend.

## 10. Known frontend limitations and issues

1. Every error box has the title "Could not load hospitals", including on the SRI and staff screens.
2. `#/request/:id` keeps polling every 3 s on network or 5xx errors and stays on a loading view. Only a 404 ends it.
3. The appointment list is fetched by phone number with no verification (a privacy gap; Backend V2 should require OTP or auth).
4. Arrival verification has no staff authentication.
5. Unknown routes (`#/login`, `#/register`, `#/authority`) silently show Home.
6. The app needs root hosting (absolute asset paths). See §1.
7. Without a backend, the console shows a `503` for each `/api/*` call made by the screen you open. This is expected; the UI shows the error message.

## 11. Verified in this handoff (14 Nov 2026)

| Check | Result |
|---|---|
| `node --check` on `app.js` and `dev-server.js` | Pass |
| Frontend alone (`npm start`, no backend) | Home, Emergency, Planned, My requests, Staff and SRI all render. API calls return 503 with a clear message. No JavaScript exceptions. |
| Through the dev proxy to the **V1** backend | Emergency search, locations, planned search (15 cardiology results), hospital detail, SRI and staff publish (200 with access code) all work. `#/request/<unknown>` gives a 404, which correctly shows "Request not found". |
| Login, registration, authority dashboard | Not present (routes fall back to Home) |
| Against **Backend V2** | **Not tested**, because Backend V2 was not available in this environment |
