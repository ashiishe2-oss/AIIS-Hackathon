# AIIS — Hackathon Final Round Demo Guide & Presentation Script
**Project:** Arogya Integrated Information System (AIIS)  
**Target Audience:** Hackathon Judges, Technical Evaluators, Healthcare Stakeholders  
**Target Duration:** 5 to 7 Minutes  
**Current Build Status:** 137/137 Tests Passing | Supabase Connected | Production Ready  

---

## 1. Quick Startup & Demo Setup

### Step 1: Start Backend V2
Open PowerShell in the primary project directory:
```powershell
cd C:\Users\ashii\OneDrive\Desktop\baackendv2
py -3.13 run.py
```
> The server will start on `http://127.0.0.1:5000`.  
> Both the frontend SPA and the backend API are served together from this single process.

### Step 2: Open Demo in Chrome
Open Google Chrome and navigate to:
```
http://localhost:5000
```
*(Tip: Press `F12` and toggle Device Toolbar `Ctrl+Shift+M` to simulate an iPhone/Android screen for the citizen emergency flow, and switch back to desktop for the hospital/authority views).*

---

## 2. Master Credentials & Quick Reference

| Role | Access Route | Credential / Code | Purpose |
| :--- | :--- | :--- | :--- |
| **Citizen (Emergency)** | `#/emergency` | *No login needed* | Zero-friction SOS hospital matching & dispatch |
| **Hospital Staff** | `#/hospital` | Access Code: `DEMO2026` | Real-time intake casualty board & OTP arrival check-in |
| **Regional Authority** | `#/authority` | *Direct navigation* | 36-facility SRI stress surveillance & zone heatmaps |
| **Citizen (Planned)** | `#/planned` | *No login needed* | Outpatient specialty search & appointment booking |
| **Registered Citizen** | `#/login` | `patient@aiis.gov.in` / `PatientPass2026!` | View historical appointments & profile |

---

## 3. The 5-Minute Judge Presentation Script

### 🕒 Minute 0:00 - 0:45 | The Problem Statement (Hook)
> *"Judges, in an emergency, every second counts. Today in India, families dial multiple hospitals or rush into ambulances blindly, only to find casualty wards full, ICU beds unavailable, or equipment down.  
>  
> Welcome to **AIIS** — the Arogya Integrated Information System. AIIS connects citizens, emergency departments, and regional health authorities into a single, real-time coordinated network with zero login barriers for patients in crisis."*

---

### 🕒 Minute 0:45 - 2:00 | Act 1: The Citizen Emergency SOS
**Action in Browser:**
1. On `http://localhost:5000`, click the red **"Find an emergency bed now"** button (or navigate to `#/emergency`).
2. Show the judges:
   - Notice **no login is required**. Immediate access.
   - Click **"Cardiac arrest / heart attack"** category.
   - Click **"Use my location"** (or select **"Majestic / City Centre"**).
3. The system instantly queries the AIIS routing engine and displays the nearest hospitals ranked by proximity, available emergency beds, and live System Reliability Index (SRI).
4. Select **"Victoria Hospital"** (or first available hospital) and click **"Tell them I'm coming"**.
5. Fill in:
   - Name: `Ramesh Kumar`
   - Phone: `+91 98765 43210`
   - Click **"Yes, tell them"**.

**Talking Points for Judges:**
> *"Look at what just happened in under 300 milliseconds:*
> 1. *A secure emergency reservation was dispatched to the hospital.*
> 2. *A real-time bed hold was placed, locking the resource for 45 minutes.*
> 3. *The citizen receives a 4-digit Arrival OTP (e.g., `4829`) and a secure QR code.*
> 4. *A privacy-preserving 64-character tracking token monitors the ambulance route without exposing personal medical records."*

---

### 🕒 Minute 2:00 - 3:15 | Act 2: Hospital Emergency Intake Desk
**Action in Browser:**
1. Open a new tab or navigate to `http://localhost:5000/#/hospital`.
2. Enter the hospital staff code: **`DEMO2026`** and click **"Enter Intake Desk"**.
3. Point to the **Live Casualty Board**:
   - Show `Ramesh Kumar` appearing at the top of the incoming queue with an active countdown timer.
   - Show patient acuity and condition details.
4. Click **"Verify Arrival"** on the patient row.
5. In the verification sheet, enter the 4-digit arrival OTP shown in Act 1, or click **"1-Tap Verify (Demo)"**.
6. Click **"Confirm Patient Arrival"**.

**Talking Points for Judges:**
> *"The moment the ambulance wheels through the casualty bay, staff verify the 4-digit OTP. The patient status instantly updates to `PATIENT_ARRIVED`.  
>  
> Notice the anti-tampering security:*
> - *The OTP is never exposed over status polling APIs.*
> - *Only authorized hospital staff can verify arrivals.*
> - *The bed count dynamically decrements to reflect an admitted patient, completely preventing double-allocation."*

---

### 🕒 Minute 3:15 - 4:15 | Act 3: Regional Health Authority Dashboard
**Action in Browser:**
1. Click **"Authority"** in the top navigation (or navigate to `http://localhost:5000/#/authority`).
2. Present the Regional SRI Command Center:
   - **Composite SRI Score:** Point out the regional health stress index (e.g., `SRI 38 - MODERATE`).
   - **Zone Aggregations:** Point out the district breakdown across Karnataka / Bengaluru (Bengaluru Central, Urban, South).
   - **Network Ledger:** Scroll down to the 36-facility grid showing live bed counts, ICU utilization, and hospital stress bands.

**Talking Points for Judges:**
> *"For regional health administrators and city emergency response commissioners, AIIS provides macro-level observability.*
>  
> *Our composite System Reliability Index (SRI) evaluates emergency bed occupancy, ICU capacity, doctor-on-duty ratios, and diversion alerts. If one sector faces an influx—like an industrial accident or flood—health authorities can divert ambulances before emergency rooms reach a crisis breaking point."*

---

### 🕒 Minute 4:15 - 5:00 | Act 4: Planned Care & Technical Wrap-Up
**Action in Browser:**
1. Click **"Planned Care"** in the navigation bar (`#/planned`).
2. Search specialty: **"Cardiology"**.
3. Show doctor visit options and click **"Request visit"** on a facility.
4. Select Date & Slot and submit.
5. Click **"Account"** or **"Visits"** to show the persisted booking.

**Closing Pitch:**
> *"AIIS handles both ends of the healthcare spectrum: zero-barrier acute emergency coordination and structured outpatient planning.  
>  
> Under the hood:  
> - **137 automated integration tests** guarantee every edge case and contract.  
> - **PostgreSQL with Row Level Security (RLS)** in Supabase ensures ironclad patient privacy.  
> - **Lightweight, mobile-first vanilla architecture** guarantees instant load times even on 2G/3G mobile networks in rural corridors.  
>  
> Thank you, and we welcome your questions!"*

---

## 4. Pre-Demo Smoke Test Checklist

Run this 30 seconds before your presentation to ensure everything is hot:

- [ ] Backend is running (`py -3.13 run.py`).
- [ ] Browser loads `http://localhost:5000` with clean UI styling.
- [ ] Emergency search returns hospitals (`Victoria Hospital`, `Bowring Hospital`).
- [ ] Emergency booking returns a 4-digit OTP and QR code.
- [ ] `#/hospital` accepts code `DEMO2026` and renders the intake queue.
- [ ] `#/authority` renders regional zones and SRI scores.

---

## 5. Troubleshooting Cheat Sheet

| Issue | Quick Fix |
| :--- | :--- |
| **Port 5000 already in use** | Run `Get-Process python \| Stop-Process -Force` in PowerShell, then re-run `py -3.13 run.py`. |
| **GPS location prompt blocked** | Use the built-in manual location dropdown (e.g. choose "Majestic / City Centre") — works instantly without browser permissions. |
| **Hospital desk says "Access Denied"** | Verify code `DEMO2026` (uppercase, no spaces). |
| **Offline demonstration needed** | Backend V2 features built-in in-memory fallback repositories; all workflows function even during intermittent network disconnects. |
