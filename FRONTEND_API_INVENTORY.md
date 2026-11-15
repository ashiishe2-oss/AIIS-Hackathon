# AIIS frontend: API inventory

This file records what the frontend (`public/app.js`) **actually sends and reads**, taken from the code. Nothing here is a proposed contract.

- **One fetch wrapper.** Every call goes through `api(path, body, headers)` (`public/app.js`, near line 27).
  - With a body, it sends `POST` with a JSON body; without one, it sends `GET`. The frontend never uses PUT, PATCH or DELETE.
  - Paths are **relative** (`/api/...`), so the browser calls the same origin that served the page. There is no base-URL setting.
  - It sends `Content-Type: application/json` and no cookies are set. The only call with an extra header is the staff bed update (`X-AIIS-Staff-Code`).
- **Errors.**
  - A non-2xx response throws an `Error` whose message is the response JSON's `error` field, or "Something went wrong. Please try again." if there is none. `e.status` holds the HTTP status.
  - A network failure shows "No connection. Check your internet and try again."
  - **So Backend V2 should return errors as `{"error": "<plain sentence for the user>"}`.** The text is shown to users as is.
- **Shape-tolerant readers.** The `norm`, `normRequest` and `normLoc` helpers (about lines 129–212) accept several field names for the same thing. The tables below list them in order of preference; the first name is what the current backend sends.

Real responses from the current (V1, Node) backend are in `reference/v1-sample-responses/`.

---

## 1. Emergency hospital search

| Field | Detail |
|---|---|
| Feature | Emergency screen and home: ranked nearest hospitals (top 3 as cards, up to 10 in total) |
| Endpoint | `/api/emergency/search` |
| Method | POST |
| Request | `{"latitude": number, "longitude": number, "category": "general", "locationName": string}`. `category` is always `"general"` in this UI. |
| Response | **Array:** `rankedHospitals`, or `results`, or `hospitals`. Each item is read with `norm()`; see **Hospital object** below. The web app does not read `quickCall`, `dataNotice` or `safetyNotice` (the Android app reads `quickCall`). |
| Auth | Public, no token |
| Caller | `loadEmergency()`. It runs on mount of `#/` and `#/emergency`, and after a GPS fix in `locate()`. Results are cached for 60 s per lat/lng. |
| Errors | Any non-2xx shows an error box with the `error` text and a Retry button. Default location if GPS is denied: Bengaluru Central (12.9716, 77.5946). |

**Ordering:** the frontend shows hospitals **in the order the backend returns them**. It does no ranking of its own. Card 1 is labelled "Nearest to you".

## 2. Locations (area picker)

| Field | Detail |
|---|---|
| Feature | "Choose area" list; naming the GPS fix ("near Rajarajeshwari Nagar") |
| Endpoint | `/api/locations` |
| Method | GET |
| Request | none |
| Response | `locations[]`, each with `name` (or `label`, `zone`), `latitude` (or `lat`, `coordinates.latitude`) and `longitude` (or `lng`, `lon`, `coordinates.longitude`). Items without a latitude are dropped. |
| Auth | Public |
| Caller | `loadLocations()` |
| Errors | Silently treated as an empty list |

## 3. Hospital details

| Field | Detail |
|---|---|
| Feature | Details sheet (address, all phone numbers, beds, departments); staff screen draft |
| Endpoint | `/api/hospitals/:id` |
| Method | GET |
| Request | none (`:id` is the hospital `id`, URL-encoded) |
| Response | `hospital` object, or the object itself, read with `norm()` |
| Auth | Public |
| Caller | `openDetails(id)` and `loadStaff()` |
| Errors | The details sheet keeps the partial data it already had. If there was none, it shows an error box. |

## 4. Planned care: hospital search

| Field | Detail |
|---|---|
| Feature | "Not an emergency": hospitals by specialty; also fills the staff screen's hospital list |
| Endpoint | `/api/planned/search` |
| Method | POST |
| Request | `{"latitude": number, "longitude": number, "specialty": string, "query": string}`. `specialty` is one of `cardiology`, `oncology`, `orthopaedics`, `neurology`, `dermatology`, `paediatrics`, `obstetrics`, `general medicine`, `diagnostics`, or `""`. `query` is a free-text hospital name. The staff screen sends `specialty: ""` and `query: ""`. |
| Response | `results[]` read with `norm()`; services come from `matchedServices` / `allServices` (see below). The UI keeps the server order and filters by `sector` (government / private) **on the client**. |
| Auth | Public |
| Caller | `planSearch()` and `loadStaff()` |
| Errors | Error box with Retry |

## 5. Emergency pre-arrival request ("Tell them I'm coming")

> This is the frontend's "SOS". It does **not** dispatch an ambulance; the ambulance button is a plain `tel:108` link. The button only appears for hospitals with `partner: true`.

| Field | Detail |
|---|---|
| Feature | Alert the hospital and hold a bed for the travel time |
| Endpoint | `/api/coordination/request` |
| Method | POST |
| Request | `{"hospitalId": string, "emergencyCategory": "general", "estimatedTravelMinutes": number, "userLocationName": string}`. No patient name or phone is sent. |
| Response (201) | `request` object, or the object itself, read with `normRequest()`; see **Coordination request object**. The `id` is stored in `localStorage["aiis.coord"]` and the page goes to `#/request/<id>`. |
| Auth | Public (anonymous) |
| Caller | `sendCoordinate(btn)` |
| Errors | The `error` text is shown inside the sheet. The current backend answers `409 {"error","code":"NOT_PARTNER"}` for non-partner hospitals. |

## 6. Emergency request tracking

| Field | Detail |
|---|---|
| Feature | Request status page with countdown, arrival code, QR and "send to family"; the live strip on other pages |
| Endpoint | `/api/coordination/:id` |
| Method | GET |
| Request | none |
| Response | `request` object, or the object itself (see below) |
| Auth | Public: anyone holding the id can read it |
| Caller | `pollRequest(id)` **polls every 3 s** while the request is open; `loadCoord()` also calls it |
| Errors | `404` shows "Request not found" and clears local state. Other errors are ignored and polling continues. |

## 7. Emergency cancellation

| Field | Detail |
|---|---|
| Feature | "Cancel request" (releases the held bed) |
| Endpoint | `/api/coordination/:id/cancel` |
| Method | POST |
| Request | `{"reason": "Cancelled by patient"}` |
| Response | `request` object, or the object itself, with `status: "CANCELLED"` |
| Auth | Public |
| Caller | action `confirm-cancel` |
| Errors | The `error` text is shown as a toast |

## 8. Arrival verification

| Field | Detail |
|---|---|
| Feature | "Confirm arrival": casualty-desk staff type the 4-digit code on the patient's phone |
| Endpoint | `/api/coordination/:id/verify-arrival` |
| Method | POST |
| Request | `{"otp": "1234"}` (string) |
| Response | `request` object, or the object itself, with `status: "PATIENT_ARRIVED"` |
| Auth | **Public**; no staff authentication in the frontend |
| Caller | form `verify` submit handler |
| Errors | The `error` text is shown in the form (current backend: `400 {"error":"Incorrect code"}`) |

## 9. Appointment (visit) request

> Only reachable for hospitals with `partner: true`. For all other hospitals, the UI shows "Call to book" or "Book on website".

| Field | Detail |
|---|---|
| Feature | Request a doctor visit (not a confirmed booking) |
| Endpoint | `/api/appointments/request` |
| Method | POST |
| Request | `{"hospitalId", "specialty", "preferredDate": "YYYY-MM-DD", "preferredTimeSlot": "Morning" or "Afternoon" or "Evening", "patientName", "patientPhone"}` |
| Response (201) | `appointment` object, or the object itself. Fields read: `id`, `hospitalName`, `receptionPhone`, `specialty`, `preferredDate`, `preferredTimeSlot`, `status`. |
| Auth | Public; identity is just the phone number typed in |
| Caller | `submitBook(form)`. The validation is client-side: a name is required and the phone must have 10 or more digits. |
| Errors | The `error` text is shown in the form |

## 10. Appointment list by phone

| Field | Detail |
|---|---|
| Feature | "My requests", the doctor-visit list |
| Endpoint | `/api/appointments?phone=<digits>` |
| Method | GET |
| Response | `appointments[]` with `id`, `hospitalId`, `hospitalName`, `receptionPhone`, `specialty`, `preferredDate`, `preferredTimeSlot`, `status` (`REQUESTED`, `CONFIRMED` or `CANCELLED`), and `patientPhone` |
| Auth | Public. **Anyone who knows a phone number can list its requests** (a known privacy gap). |
| Caller | `refreshAppts()` on mount of `#/me`, once per phone number saved on the device |
| Errors | Ignored; the local copy is kept |

## 11. Appointment cancellation

| Field | Detail |
|---|---|
| Endpoint | `/api/appointments/:id/cancel` |
| Method | POST |
| Request | `{"reason": "Cancelled by patient"}` |
| Response | Not read; success just marks the local copy as `CANCELLED` |
| Auth | Public |
| Caller | action `cancel-appt` |
| Errors | The `error` text is shown as a toast |

## 12. Hospital capacity update (staff)

| Field | Detail |
|---|---|
| Feature | `#/hospital`, "Update beds and readiness" |
| Endpoint | `/api/hospitals/:id/capacity` |
| Method | POST |
| Request | Only the counts the staff member changed: `{"emergencyBeds": {"available": n}?, "icuBeds": {"available": n}?, "departments": [{"name","status"}], "equipment": [{"name","status"}]}`. Department status is `Ready`, `Limited` or `Closed`; equipment status is `Available`, `Limited` or `Not available`. |
| Headers | `X-AIIS-Staff-Code: <code typed by staff>`. It is kept in memory only, never stored. |
| Response | `hospital` object, or the object itself, read with `norm()`. The toast reads `capacity.emergencyBeds.available`. |
| Auth | **Shared access code header, not a JWT.** The current backend answers 403 if the server has no code configured, and 401 if the code is wrong. |
| Caller | `staffPublish(btn)`; the hospital list comes from `/api/planned/search`, then the draft from `/api/hospitals/:id` |
| Errors | The `error` text is shown as a toast. Without a code, the UI blocks the call with "Enter your staff access code first." |

## 13. Regional SRI (Strain Risk Index)

| Field | Detail |
|---|---|
| Feature | `#/sri`, a list of areas ranked by forecast pressure |
| Endpoint | `/api/sri/regional` |
| Method | GET |
| Response | `sri` (or the root), which is either an array or an object with `zones`, `regions`, `areas` or `districts`, plus optional `region`, `horizonDays` and `generatedAt`. Each zone has: `zone` (or `name`, `region`, `area`); `sri` (or `score`, `index`, `value`, `riskScore`), as 0–1 or 0–100, where values above 1 are divided by 100; and `level` (or `band`, `risk`). |
| Auth | Public |
| Caller | `loadSri()` |
| Errors | Error box with Retry (titled "Could not load hospitals", a known copy issue) |

## Not present in this frontend

There is **no** registration, login, logout, session, JWT, guest token or refresh flow. There is also **no** authority or government dashboard and no SOS dispatch API. The routes `#/login`, `#/register` and `#/authority` fall back to the home screen. Backend V2 endpoints for these need new frontend screens, which is out of scope for this handoff.

---

## Shared object shapes

### Hospital object (read by `norm()`)

| UI use | Fields read, in order of preference |
|---|---|
| Identity | `id`, `name`, `campus`, `type`, `sector` (contains "government" or "private"), `zone`, `address` |
| Map / directions | `coordinates.latitude` or `location.lat` or `latitude`; `coordinates.longitude` or `location.lng` / `lon` or `longitude` |
| Call buttons | `emergencyPhone`, then `casualtyPhone`, `phone`, `receptionPhone` (emergency call); `receptionPhone`, then `phone`, `emergencyPhone` (booking call) |
| Phone labels | `emergencyPhoneLabel`, `receptionPhoneLabel`, `phones[] {label, number}` (details sheet) |
| Number trust | `phoneStatus`: `"listing"` adds "Number from a public list. If no one answers, call 108." `source {label, url}` gives "Source: …, checked …". `website` gives "Book on website". |
| Travel | `transitMins` (or `transitMinutes`, `etaMinutes`, `travelMinutes`); `distanceKm` (or `distance`) |
| Scope | `emergencyScope` (`general`, `cardiac`, `neuro`, `trauma`, `children` or `maternity`); `scopeNote` (text) |
| Partner gating | `partner` (boolean). Only `true` shows "Tell them I'm coming" and "Request visit". |
| Beds | `capacity` (or `beds`, `liveCapacity`), with `.emergencyBeds` (or `.emergency`, `.er`, `.casualty`) and `.icuBeds` (or `.icu`). Each is `{available (or free, vacant, count), total (or capacity, max)}` or a number. Also `emergencyBedsAvailable` and `icuBedsAvailable`. **`null` or missing means "call to check".** |
| Holds | `capacity.provisionalHolds` (or `holds`) |
| Facilities | `emergencyFacilities` (or `facilities`, `emergencyServices`, `capabilities`): strings, `{name}` objects or a map |
| Departments | `departments[] {name, status, onDuty}` (or `departmentReadiness`) |
| Equipment | `equipment[] {name, status}` (or `equipmentAvailability`) |
| Services | `matchedServices`, `plannedServices` or `allServices`, as `[{specialty, consultants?, waitDays?}]`; counts are shown only if present |
| Freshness | `dataFreshness.lastUpdated` (beds "published … ago"), `.phonesChecked` (date), `.isSimulated` or a `source` containing "demo" (shows a "Demo data" badge) |
| Why ranked | `rationale[]` (or `rankingRationale`, `whyRanked`, `reasons`, `explanation`, `rankReasons`) |

### Coordination request object (read by `normRequest()`)

| UI use | Fields read |
|---|---|
| Identity | `id` (or `requestId`), `hospitalId`, `hospitalName`, `hospitalAddress`, `emergencyPhone` (or `hospitalPhone`) |
| Status | `status`, one of `REQUEST_SUBMITTED`, `AWAITING_HOSPITAL_RESPONSE`, `HOSPITAL_ACCEPTED`, `ARRIVAL_VERIFICATION_PENDING`, `PATIENT_ARRIVED`, `CANCELLED`, `EXPIRED`. The last three end polling. |
| Arrival code | `otp` (or `arrivalOtp`, `verificationCode`, `pass.otp`). Shown to the patient and encoded in the QR code. |
| Countdown | `holdExpiresAt` (or `provisionalHold.expiresAt`, `expiresAt`). Fallback: `createdAt` + (`estimatedTravelMinutes` + 15) minutes. |

---

## Other API client (not in this package): Android app v1.2

`org.aiis.app.EmergencyActivity.fetchNearest()` calls `POST https://aiis-livid.vercel.app/api/emergency/search`. The URL is hard-coded in `App.BASE_URL`.

- **Request:** `{"latitude", "longitude", "category": "general"}`.
- **Fields it reads:** first `quickCall {name, phone, transitMins}`. Otherwise `rankedHospitals[]` (or `results[]`), taking the first item with `capacity.emergencyBeds.available > 0` and a phone, else the first item, with `name`, `transitMins` and `emergencyPhone`, `casualtyPhone`, `phone` or `receptionPhone`.
- **WebView:** the rest of the Android app is a WebView of the same web frontend.
