# AIIS — Arogya Infrastructure Intelligence System

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.x-green.svg)](https://flask.palletsprojects.com/)
[![Database](https://img.shields.io/badge/Database-Supabase%20PostgreSQL-3ECF8E.svg)](https://supabase.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)](#license)

**Arogya Infrastructure Intelligence System (AIIS)** is a next-generation healthcare coordination and infrastructure intelligence platform engineered for emergency operations, real-time hospital bed capacity tracking, intelligent dispatch matching, and multilingual patient access.

---

## 🏛️ System Architecture

AIIS bridges citizen emergency healthcare needs with real-time public hospital capacity through a unified multi-tier architecture:

```
                            ┌──────────────────────────────────────────┐
                            │        Multilingual Client Web App       │
                            │   (Vanilla ES6+ SPA, Hash Router, PWA)   │
                            │             public/ & frontend/          │
                            └────────────────────┬─────────────────────┘
                                                 │
                                                 ▼
                            ┌──────────────────────────────────────────┐
                            │         Unified API & Web Entry          │
                            │       (run.py / api/index.py / Flask)    │
                            └────────────────────┬─────────────────────┘
                                                 │
                 ┌───────────────────────────────┴───────────────────────────────┐
                 ▼                                                               ▼
  ┌───────────────────────────────┐                               ┌───────────────────────────────┐
  │   Middleware & Security       │                               │   AIIS Backend V2 Core        │
  │   - JWT / RBAC Authorization  │                               │   - Emergency Matching & SOS  │
  │   - Tracking Token Hashing    │                               │   - Live Bed Capacity (SRI)   │
  │   - Request Payload Validation│                               │   - Outpatient Appointments   │
  └──────────────┬────────────────┘                               └──────────────┬────────────────┘
                 │                                                               │
                 └───────────────────────────────┬───────────────────────────────┘
                                                 │
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │    Supabase PostgreSQL      │
                                  │    - Row-Level Security     │
                                  │    - Capacity History Trg   │
                                  │    - Realtime Event Streams │
                                  └─────────────────────────────┘
```

### Key Components

- **`backend_v2/`**: Modular Flask backend adhering to strict layer separation (Routes, Services, Repositories, Schemas, Middleware).
- **`public/`**: Fast, lightweight, zero-dependency multilingual frontend SPA (English, Kannada, Hindi, Tamil, Telugu, Malayalam, Marathi, Bengali, Gujarati, Odia, Urdu).
- **`i18n-src/`**: Raw translation dictionaries and build script for multilingual compilation.
- **`api/`**: Serverless deployment entrypoint for Vercel Python runtime (`api/index.py`).
- **`backend_v2/database/`**: 12 modular SQL migrations and seed scripts establishing Row-Level Security (RLS) policies and table schemas.

---

## 📂 Repository Structure

```
AIIS_WEBSITE_MULTILINGUAL/
├── api/
│   └── index.py                    # Vercel serverless entrypoint
├── backend_v2/
│   ├── app.py                      # Flask application factory
│   ├── config.py                   # Environment configuration loader
│   ├── extensions.py               # Supabase and cross-cutting extensions
│   ├── data/                       # Verified Karnataka public hospital dataset
│   │   ├── hospitals.csv
│   │   └── verified_hospitals.json
│   ├── database/                   # Schema migrations and seed SQL
│   │   ├── migrations/             # 001 through 012 RLS migrations
│   │   └── seeds/                  # Hospital directory seed scripts
│   ├── middleware/                 # Auth, RBAC, and payload validation
│   ├── repositories/               # Data access layer (Supabase / offline fallbacks)
│   ├── routes/                     # Blueprint endpoints (emergency, capacity, auth, etc.)
│   ├── schemas/                    # Request/response validation schemas
│   ├── services/                   # Domain orchestration and dispatch logic
│   ├── tests/                      # Automated pytest unit and integration test suite
│   ├── utils/                      # Response wrappers, validators, coordinate math
│   └── README.md                   # Backend-specific architecture guide
├── frontend/                       # Supplementary staff/admin templates and assets
├── public/                         # Production-ready citizen web application (SPA)
│   ├── app.js                      # Core frontend application bundle
│   ├── i18n.js                     # Multilingual translation engine
│   ├── styles.css                  # Responsive design stylesheet
│   ├── i18n/                       # Compiled localized JSON strings (11 languages)
│   └── vendor/                     # Vendored client libraries (qrcode.js)
├── i18n-src/                       # Raw source language files and build script
├── .env.example                    # Template environment variables (safe placeholders)
├── .gitignore                      # Comprehensive Git exclusion rules
├── .vercelignore                   # Cloud deployment ignore rules
├── dev-server.js                   # Lightweight Node.js static server & API proxy
├── package.json                    # Frontend development scripts
├── requirements.txt                # Root Python dependencies
├── run.py                          # Canonical Flask local server entrypoint
└── vercel.json                     # Vercel deployment configuration
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites

- Python 3.10+ (Python 3.11, 3.12, or 3.13 recommended)
- Node.js 18+ (optional, for running standalone `dev-server.js`)
- Git

### 2. Environment Configuration

Clone the repository and create your local environment file:

```bash
cp .env.example .env
```

Edit `.env` with your specific settings:

```dotenv
FLASK_ENV=development
FLASK_SECRET_KEY=generate_with_python_secrets_token_hex_32
SUPABASE_URL=https://<your-project-ref>.supabase.co
SUPABASE_ANON_KEY=your_public_anon_key
SUPABASE_SERVICE_ROLE_KEY=your_private_service_role_key
CORS_ORIGINS=http://localhost:5000,http://localhost:8080,http://127.0.0.1:5000
```

> [!NOTE]
> AIIS includes built-in offline fallbacks using verified hospital data. You can run the application locally even without active Supabase credentials.

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install -r requirements.txt
```

### 4. Run the Application

Start the integrated full-stack server (serves both API and Web App on port 5000):

```bash
python run.py
```

- **Citizen Web App:** [http://localhost:5000/](http://localhost:5000/)
- **API Health Check:** [http://localhost:5000/api/health](http://localhost:5000/api/health)

Alternatively, for decoupled frontend development with hot static reloading:

```bash
# Terminal 1: Run Backend
python run.py

# Terminal 2: Run Dev Server (proxies /api to :5000)
node dev-server.js
```

---

## 🧪 Testing & Verification

Run the automated test suite using pytest:

```bash
# Run unit and contract test suites (138+ automated checks)
pytest backend_v2/tests -k "not inspect_remote_schema and not post_deployment_rls_verifier and not run_remote_audit and not test_live_emergency_lifecycle"
```

To run remote integration verifications against a live Supabase instance:

```bash
# Ensure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set in .env
python -m backend_v2.tests.post_deployment_rls_verifier
```

---

## 📚 Technical Documentation Index

Detailed architectural and operational documentation is available in the repository:

| Document | Purpose |
| :--- | :--- |
| [AIIS_TECHNICAL_ARCHITECTURE.md](AIIS_TECHNICAL_ARCHITECTURE.md) | In-depth technical architecture, data flows, and layer design |
| [AIIS_INTEGRATION_CONTRACT.md](AIIS_INTEGRATION_CONTRACT.md) | Exhaustive API contract between frontend SPA and Backend V2 |
| [AIIS_HACKATHON_DEMO_GUIDE.md](AIIS_HACKATHON_DEMO_GUIDE.md) | Step-by-step demo presentation guide and test walkthrough |
| [AIIS_FINAL_INTEGRATION_REPORT.md](AIIS_FINAL_INTEGRATION_REPORT.md) | Final integration report, schema migrations, and test matrix |
| [FRONTEND_API_INVENTORY.md](FRONTEND_API_INVENTORY.md) | Complete frontend endpoint catalog and payload structures |
| [FRONTEND_INTEGRATION_NOTES.md](FRONTEND_INTEGRATION_NOTES.md) | Integration notes and contract harmonization details |
| [HANDOFF_REPORT.md](HANDOFF_REPORT.md) | Frontend handoff documentation and tech stack breakdown |
| [backend_v2/README.md](backend_v2/README.md) | Backend V2 specific architecture and stage completion status |

---

## 🔒 Security Best Practices

- **Never Commit Secrets:** Sensitive credentials (`.env`, service-role keys, private certificates) are strictly excluded via `.gitignore`.
- **Row-Level Security (RLS):** Supabase PostgreSQL tables are protected by comprehensive RLS policies preventing cross-tenant or cross-patient access.
- **Tracking Token Privacy:** Emergency citizen tracking tokens are stored solely as cryptographic SHA-256 hashes in the database.
- **Role Isolation:** Explicit RBAC middleware enforces strict role verification (`patient`, `hospital_admin`, `authority`, `platform_admin`).
