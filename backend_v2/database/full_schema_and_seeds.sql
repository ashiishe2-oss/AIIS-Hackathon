-- =====================================================================
-- AIIS BACKEND V2 - CONSOLIDATED DATABASE SCHEMA & SEED SCRIPT
-- Target Project: romwnlabuhsnxuomhevb (Supabase PostgreSQL)
-- =====================================================================

-- >>> MIGRATION: 001_create_profiles.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 001: User Profiles
-- ==============================================================================
-- Description: Establishes application profile entity linked to Supabase Auth.
-- Security: Never stores passwords. Role assignment strictly server-managed.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Note: auth.users is natively managed by Supabase Auth (GoTrue).
-- public.profiles links directly to auth.users(id).
-- ------------------------------------------------------------------------------

-- Profiles Table
CREATE TABLE IF NOT EXISTS public.profiles (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    full_name VARCHAR(255) NOT NULL,
    phone VARCHAR(32),
    role VARCHAR(32) NOT NULL DEFAULT 'patient' 
        CHECK (role IN ('patient', 'hospital_admin', 'authority', 'platform_admin')),
    hospital_id INTEGER, -- Foreign key constraint attached after hospitals table creation
    account_status VARCHAR(32) NOT NULL DEFAULT 'active' 
        CHECK (account_status IN ('active', 'suspended', 'pending_approval')),
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Ensure email column exists even if table was created in an earlier migration
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

CREATE INDEX IF NOT EXISTS idx_profiles_email 
ON public.profiles (email) 
WHERE email IS NOT NULL;

-- Trigger function for auto-updating updated_at
CREATE OR REPLACE FUNCTION public.set_current_timestamp_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_profiles_updated_at ON public.profiles;
CREATE TRIGGER trg_profiles_updated_at
    BEFORE UPDATE ON public.profiles
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.profiles IS 'Application user profiles linked to Supabase Auth identities.';
COMMENT ON COLUMN public.profiles.role IS 'Role authorization claim verified server-side.';
COMMENT ON COLUMN public.profiles.hospital_id IS 'Target hospital authorization anchor for hospital_admin users.';


-- <<< END MIGRATION: 001_create_profiles.sql <<<

-- >>> MIGRATION: 002_create_hospitals.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 002: Hospitals Directory
-- ==============================================================================
-- Description: Core public healthcare infrastructure registry.
-- Notice: Directory records represent registered infrastructure, not live availability.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.hospitals (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    address TEXT NOT NULL,
    city VARCHAR(100) NOT NULL,
    district VARCHAR(100) NOT NULL,
    state VARCHAR(100) NOT NULL DEFAULT 'Karnataka',
    postal_code VARCHAR(20),
    latitude NUMERIC(10, 6) NOT NULL CHECK (latitude BETWEEN -90.0 AND 90.0),
    longitude NUMERIC(10, 6) NOT NULL CHECK (longitude BETWEEN -180.0 AND 180.0),
    contact_number VARCHAR(32),
    emergency_phone VARCHAR(32),
    verification_status VARCHAR(32) NOT NULL DEFAULT 'unverified' 
        CHECK (verification_status IN ('verified', 'unverified', 'pending')),
    operational_status VARCHAR(32) NOT NULL DEFAULT 'operational' 
        CHECK (operational_status IN ('operational', 'overwhelmed', 'diverting', 'closed')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Safely link profiles.hospital_id to hospitals.id
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints 
        WHERE constraint_name = 'fk_profiles_hospital' AND table_name = 'profiles'
    ) THEN
        ALTER TABLE public.profiles 
            ADD CONSTRAINT fk_profiles_hospital 
            FOREIGN KEY (hospital_id) REFERENCES public.hospitals(id) ON DELETE SET NULL;
    END IF;
END $$;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_hospitals_updated_at ON public.hospitals;
CREATE TRIGGER trg_hospitals_updated_at
    BEFORE UPDATE ON public.hospitals
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.hospitals IS 'Public hospital infrastructure registry containing verified facility coordinates and administrative boundaries.';
COMMENT ON COLUMN public.hospitals.verification_status IS 'Whether facility identity and physical location have been officially validated.';


-- <<< END MIGRATION: 002_create_hospitals.sql <<<

-- >>> MIGRATION: 003_create_hospital_capabilities.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 003: Hospital Clinical Capabilities
-- ==============================================================================
-- Description: Tracks specialized clinical intake readiness per facility.
-- Rule: Capabilities default to 'unknown' until validated by health authority.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.hospital_capabilities (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    capability_name VARCHAR(64) NOT NULL CHECK (
        capability_name IN (
            'emergency_receiving',
            'icu',
            'trauma',
            'cardiac',
            'stroke_neuro',
            'paediatric',
            'respiratory_emergencies',
            'burns',
            'maternal'
        )
    ),
    verification_state VARCHAR(32) NOT NULL DEFAULT 'unknown' 
        CHECK (verification_state IN ('verified', 'unverified', 'unknown')),
    details JSONB DEFAULT '{}'::jsonb NOT NULL,
    verified_at TIMESTAMPTZ,
    verified_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_hospital_capability UNIQUE (hospital_id, capability_name)
);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_hospital_capabilities_updated_at ON public.hospital_capabilities;
CREATE TRIGGER trg_hospital_capabilities_updated_at
    BEFORE UPDATE ON public.hospital_capabilities
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.hospital_capabilities IS 'Clinical specialties and emergency intake capabilities per hospital.';
COMMENT ON COLUMN public.hospital_capabilities.verification_state IS 'Explicit verification state: verified, unverified, or unknown.';


-- <<< END MIGRATION: 003_create_hospital_capabilities.sql <<<

-- >>> MIGRATION: 004_create_hospital_capacity.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 004: Hospital Capacity & Historical Ledger
-- ==============================================================================
-- Description: Current real-time capacity and immutable historical capacity ledger.
-- Data Integrity: Strict mathematical constraints enforce bed and ICU balance.
-- ==============================================================================

-- 1. Current Live Capacity Snapshot Table
CREATE TABLE IF NOT EXISTS public.hospital_capacity (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL UNIQUE REFERENCES public.hospitals(id) ON DELETE CASCADE,
    total_beds INTEGER NOT NULL DEFAULT 0 CHECK (total_beds >= 0),
    available_beds INTEGER NOT NULL DEFAULT 0 CHECK (available_beds >= 0),
    occupied_beds INTEGER NOT NULL DEFAULT 0 CHECK (occupied_beds >= 0),
    provisionally_allocated_beds INTEGER NOT NULL DEFAULT 0 CHECK (provisionally_allocated_beds >= 0),
    icu_total INTEGER NOT NULL DEFAULT 0 CHECK (icu_total >= 0),
    icu_available INTEGER NOT NULL DEFAULT 0 CHECK (icu_available >= 0),
    icu_occupied INTEGER NOT NULL DEFAULT 0 CHECK (icu_occupied >= 0),
    ventilators_total INTEGER NOT NULL DEFAULT 0 CHECK (ventilators_total >= 0),
    ventilators_available INTEGER NOT NULL DEFAULT 0 CHECK (ventilators_available >= 0),
    oxygen_status VARCHAR(32) NOT NULL DEFAULT 'unknown' 
        CHECK (oxygen_status IN ('adequate', 'low', 'critical', 'unavailable', 'unknown')),
    emergency_receiving_status VARCHAR(32) NOT NULL DEFAULT 'unknown' 
        CHECK (emergency_receiving_status IN ('available', 'busy', 'diverting', 'closed', 'unknown')),
    verified_specialist_availability JSONB DEFAULT '{}'::jsonb NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'unknown' 
        CHECK (status IN ('available', 'occupied', 'provisionally_allocated', 'unavailable', 'unknown')),
    updated_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    
    -- Mathematical sanity constraints
    CONSTRAINT chk_total_beds_sum 
        CHECK (occupied_beds + available_beds + provisionally_allocated_beds <= total_beds),
    CONSTRAINT chk_icu_beds_sum 
        CHECK (icu_occupied + icu_available <= icu_total),
    CONSTRAINT chk_ventilators_sum 
        CHECK (ventilators_available <= ventilators_total)
);

-- Trigger for updated_at on current capacity
DROP TRIGGER IF EXISTS trg_hospital_capacity_updated_at ON public.hospital_capacity;
CREATE TRIGGER trg_hospital_capacity_updated_at
    BEFORE UPDATE ON public.hospital_capacity
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();


-- 2. Historical Capacity Ledger (Append-Only)
CREATE TABLE IF NOT EXISTS public.hospital_capacity_history (
    id BIGSERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    total_beds INTEGER NOT NULL,
    available_beds INTEGER NOT NULL,
    occupied_beds INTEGER NOT NULL,
    provisionally_allocated_beds INTEGER NOT NULL,
    icu_total INTEGER NOT NULL,
    icu_available INTEGER NOT NULL,
    icu_occupied INTEGER NOT NULL,
    ventilators_total INTEGER NOT NULL,
    ventilators_available INTEGER NOT NULL,
    oxygen_status VARCHAR(32) NOT NULL,
    emergency_receiving_status VARCHAR(32) NOT NULL,
    verified_specialist_availability JSONB NOT NULL,
    status VARCHAR(32) NOT NULL,
    change_reason VARCHAR(255),
    recorded_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Automated trigger function to record historical telemetry on any change
CREATE OR REPLACE FUNCTION public.archive_capacity_snapshot()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.hospital_capacity_history (
        hospital_id,
        total_beds,
        available_beds,
        occupied_beds,
        provisionally_allocated_beds,
        icu_total,
        icu_available,
        icu_occupied,
        ventilators_total,
        ventilators_available,
        oxygen_status,
        emergency_receiving_status,
        verified_specialist_availability,
        status,
        recorded_by,
        recorded_at
    ) VALUES (
        NEW.hospital_id,
        NEW.total_beds,
        NEW.available_beds,
        NEW.occupied_beds,
        NEW.provisionally_allocated_beds,
        NEW.icu_total,
        NEW.icu_available,
        NEW.icu_occupied,
        NEW.ventilators_total,
        NEW.ventilators_available,
        NEW.oxygen_status,
        NEW.emergency_receiving_status,
        NEW.verified_specialist_availability,
        NEW.status,
        NEW.updated_by,
        NEW.updated_at
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_archive_capacity_history ON public.hospital_capacity;
CREATE TRIGGER trg_archive_capacity_history
    AFTER INSERT OR UPDATE ON public.hospital_capacity
    FOR EACH ROW EXECUTE FUNCTION public.archive_capacity_snapshot();

COMMENT ON TABLE public.hospital_capacity IS 'Current operational capacity telemetry per facility with strict balance validation.';
COMMENT ON TABLE public.hospital_capacity_history IS 'Append-only historical capacity ledger used for Strain Risk Index (SRI) trend analysis.';


-- <<< END MIGRATION: 004_create_hospital_capacity.sql <<<

-- >>> MIGRATION: 005_create_emergency_requests.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 005: Emergency Requests (SOS)
-- ==============================================================================
-- Description: Citizen Emergency SOS requests with cryptographic guest security.
-- Security: Stores SHA-256 hash of tracking tokens. Never stores plaintext bearer tokens.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.emergency_requests (
    id VARCHAR(36) PRIMARY KEY,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    hospital_id INTEGER REFERENCES public.hospitals(id) ON DELETE SET NULL,
    target_hospital_id INTEGER REFERENCES public.hospitals(id) ON DELETE SET NULL,
    guest_reference VARCHAR(64),
    tracking_token_hash VARCHAR(128), -- SHA-256 hash of high-entropy citizen token
    patient_name VARCHAR(128) DEFAULT 'Patient',
    companion_name VARCHAR(128),
    emergency_category VARCHAR(64) NOT NULL DEFAULT 'other_unsure' CHECK (
        emergency_category IN (
            'cardiac',
            'stroke_neuro',
            'trauma',
            'breathing',
            'paediatric',
            'other_unsure'
        )
    ),
    severity VARCHAR(32) NOT NULL DEFAULT 'HIGH' 
        CHECK (severity IN ('CRITICAL', 'HIGH', 'MODERATE', 'LOW')),
    status VARCHAR(64) NOT NULL DEFAULT 'pending' 
        CHECK (status IN (
            'pending',
            'acknowledged',
            'accepted',
            'declined',
            'expired',
            'cancelled',
            'completed',
            'REQUEST_SUBMITTED'
        )),
    description TEXT,
    notes TEXT,
    cancellation_reason TEXT,
    latitude NUMERIC(10, 6) CHECK (latitude BETWEEN -90.0 AND 90.0),
    longitude NUMERIC(10, 6) CHECK (longitude BETWEEN -180.0 AND 180.0),
    location_description TEXT,
    user_location_name VARCHAR(128),
    contact_phone VARCHAR(32),
    estimated_travel_minutes INTEGER DEFAULT 15 CHECK (estimated_travel_minutes >= 0),
    otp VARCHAR(8),
    otp_code_hash VARCHAR(128), -- Cryptographic hash of arrival code
    expires_at TIMESTAMPTZ, -- Expiry timestamp for provisional hospital bed hold
    hold_expires_at TIMESTAMPTZ, -- Hold expiration timestamp
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Ensure hold_expires_at exists even if table was created in an earlier migration
ALTER TABLE public.emergency_requests 
ADD COLUMN IF NOT EXISTS hold_expires_at TIMESTAMPTZ;

-- Trigger for updated_at
DROP TRIGGER IF EXISTS trg_emergency_requests_updated_at ON public.emergency_requests;
CREATE TRIGGER trg_emergency_requests_updated_at
    BEFORE UPDATE ON public.emergency_requests
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.emergency_requests IS 'Citizen emergency SOS requests with secure guest tracking token hashes.';
COMMENT ON COLUMN public.emergency_requests.tracking_token_hash IS 'SHA-256 hash of the high-entropy guest access token. Client presents plaintext; server verifies hash.';
COMMENT ON COLUMN public.emergency_requests.expires_at IS 'Expiration time for provisional triage and dispatch bed hold.';


-- <<< END MIGRATION: 005_create_emergency_requests.sql <<<

-- >>> MIGRATION: 006_create_emergency_request_events.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 006: Emergency Request Events (Audit Ledger)
-- ==============================================================================
-- Description: Immutable audit log tracking state transitions and telemetry events.
-- Security: Append-only table. Updates and deletes are prohibited.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.emergency_request_events (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL REFERENCES public.emergency_requests(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL CHECK (
        event_type IN (
            'request_created',
            'hospital_notified',
            'hospital_acknowledged',
            'hospital_accepted',
            'hospital_declined',
            'request_expired',
            'request_cancelled',
            'request_completed',
            'arrival_verified'
        )
    ),
    actor_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    actor_role VARCHAR(32) NOT NULL DEFAULT 'system',
    metadata JSONB DEFAULT '{}'::jsonb NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

COMMENT ON TABLE public.emergency_request_events IS 'Immutable chronological audit log for emergency dispatch lifecycle events.';
COMMENT ON COLUMN public.emergency_request_events.metadata IS 'Structured audit payload (e.g. coordinates, decline reason, triage notes).';


-- <<< END MIGRATION: 006_create_emergency_request_events.sql <<<

-- >>> MIGRATION: 007_create_hospital_request_responses.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 007: Hospital Request Responses
-- ==============================================================================
-- Description: Dispatches sent to hospitals and their individual response status.
-- Integrity: Enforces unique constraint per (request_id, hospital_id).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.hospital_request_responses (
    id BIGSERIAL PRIMARY KEY,
    request_id VARCHAR(36) NOT NULL REFERENCES public.emergency_requests(id) ON DELETE CASCADE,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    response_status VARCHAR(32) NOT NULL DEFAULT 'notified' 
        CHECK (response_status IN ('notified', 'acknowledged', 'accepted', 'declined', 'timed_out')),
    response_notes TEXT,
    provisional_allocation JSONB DEFAULT '{}'::jsonb NOT NULL,
    responded_by UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    notified_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    responded_at TIMESTAMPTZ,
    CONSTRAINT uq_request_hospital UNIQUE (request_id, hospital_id)
);

COMMENT ON TABLE public.hospital_request_responses IS 'Multi-hospital notification and response tracking for coordinated emergency triage.';
COMMENT ON COLUMN public.hospital_request_responses.provisional_allocation IS 'Provisional bed/equipment hold details (e.g. hold duration, assigned ward).';


-- <<< END MIGRATION: 007_create_hospital_request_responses.sql <<<

-- >>> MIGRATION: 008_create_normal_healthcare.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 008: Normal Healthcare Entities
-- ==============================================================================
-- Description: Department readiness, diagnostic equipment, and outpatient appointments.
-- Supported by frontend: #/hospital (Staff readiness) & #/planned (Appointments).
-- ==============================================================================

-- 1. Hospital Departments & Operational Readiness
CREATE TABLE IF NOT EXISTS public.hospital_departments (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Ready' 
        CHECK (status IN ('Ready', 'Limited', 'Closed')),
    doctors_on_duty INTEGER DEFAULT 1 CHECK (doctors_on_duty >= 0),
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_hospital_department UNIQUE (hospital_id, name)
);

-- 2. Hospital Diagnostic & Clinical Equipment Availability
CREATE TABLE IF NOT EXISTS public.hospital_equipment (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Available' 
        CHECK (status IN ('Available', 'Limited', 'Not available')),
    total_units INTEGER DEFAULT 1 CHECK (total_units >= 0),
    available_units INTEGER DEFAULT 1 CHECK (available_units >= 0),
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_hospital_equipment UNIQUE (hospital_id, name),
    CONSTRAINT chk_equipment_units CHECK (available_units <= total_units)
);

-- 3. Outpatient Consultation Appointments
CREATE TABLE IF NOT EXISTS public.appointments (
    id VARCHAR(36) PRIMARY KEY, -- e.g. APT-XXXXXX
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    patient_name VARCHAR(128) NOT NULL,
    patient_phone VARCHAR(32) NOT NULL,
    patient_age VARCHAR(16),
    specialty VARCHAR(128) NOT NULL,
    preferred_date DATE NOT NULL,
    preferred_time_slot VARCHAR(64) NOT NULL,
    notes TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED' 
        CHECK (status IN ('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Triggers for updated_at
DROP TRIGGER IF EXISTS trg_hospital_departments_updated_at ON public.hospital_departments;
CREATE TRIGGER trg_hospital_departments_updated_at
    BEFORE UPDATE ON public.hospital_departments
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

DROP TRIGGER IF EXISTS trg_hospital_equipment_updated_at ON public.hospital_equipment;
CREATE TRIGGER trg_hospital_equipment_updated_at
    BEFORE UPDATE ON public.hospital_equipment
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

DROP TRIGGER IF EXISTS trg_appointments_updated_at ON public.appointments;
CREATE TRIGGER trg_appointments_updated_at
    BEFORE UPDATE ON public.appointments
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.hospital_departments IS 'Departmental operational readiness published by casualty/hospital staff.';
COMMENT ON TABLE public.hospital_equipment IS 'Key life-support and diagnostic equipment availability.';
COMMENT ON TABLE public.appointments IS 'Citizen-scheduled OPD and specialty consultations.';


-- <<< END MIGRATION: 008_create_normal_healthcare.sql <<<

-- >>> MIGRATION: 009_create_indexes_and_constraints.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 009: Indexes & Performance Constraints
-- ==============================================================================
-- Description: Creates optimized B-Tree and composite indexes for high-throughput
-- queries, spatial proximity lookups, and fast foreign key joins.
-- ==============================================================================

-- 1. Hospitals Directory & Spatial Discovery
CREATE INDEX IF NOT EXISTS idx_hospitals_city_district 
    ON public.hospitals (city, district);

CREATE INDEX IF NOT EXISTS idx_hospitals_coordinates 
    ON public.hospitals (latitude, longitude);

CREATE INDEX IF NOT EXISTS idx_hospitals_operational 
    ON public.hospitals (operational_status, verification_status);

-- 2. User Profiles
CREATE INDEX IF NOT EXISTS idx_profiles_role 
    ON public.profiles (role);

CREATE INDEX IF NOT EXISTS idx_profiles_hospital 
    ON public.profiles (hospital_id) 
    WHERE hospital_id IS NOT NULL;

-- 3. Hospital Capabilities
CREATE INDEX IF NOT EXISTS idx_capabilities_lookup 
    ON public.hospital_capabilities (capability_name, verification_state);

CREATE INDEX IF NOT EXISTS idx_capabilities_hospital 
    ON public.hospital_capabilities (hospital_id);

-- 4. Hospital Capacity & Telemetry History
CREATE INDEX IF NOT EXISTS idx_capacity_hospital 
    ON public.hospital_capacity (hospital_id);

CREATE INDEX IF NOT EXISTS idx_capacity_receiving 
    ON public.hospital_capacity (emergency_receiving_status, available_beds);

CREATE INDEX IF NOT EXISTS idx_capacity_history_timeline 
    ON public.hospital_capacity_history (hospital_id, recorded_at DESC);

-- 5. Emergency Requests (SOS)
CREATE INDEX IF NOT EXISTS idx_emergency_status_created 
    ON public.emergency_requests (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_emergency_target_hospital 
    ON public.emergency_requests (target_hospital_id, status) 
    WHERE target_hospital_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_emergency_patient 
    ON public.emergency_requests (patient_id) 
    WHERE patient_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_emergency_guest_ref 
    ON public.emergency_requests (guest_reference) 
    WHERE guest_reference IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_emergency_hold_expiry 
    ON public.emergency_requests (hold_expires_at) 
    WHERE status IN ('pending', 'acknowledged', 'accepted');

-- 6. Emergency Audit Events Ledger
CREATE INDEX IF NOT EXISTS idx_emergency_events_request 
    ON public.emergency_request_events (request_id, created_at ASC);

CREATE INDEX IF NOT EXISTS idx_emergency_events_type 
    ON public.emergency_request_events (event_type);

-- 7. Hospital Responses & Dispatches
CREATE INDEX IF NOT EXISTS idx_responses_hospital_status 
    ON public.hospital_request_responses (hospital_id, response_status);

CREATE INDEX IF NOT EXISTS idx_responses_request 
    ON public.hospital_request_responses (request_id);

-- 8. Normal Healthcare (Departments, Equipment, Appointments)
CREATE INDEX IF NOT EXISTS idx_departments_hospital 
    ON public.hospital_departments (hospital_id, status);

CREATE INDEX IF NOT EXISTS idx_equipment_hospital 
    ON public.hospital_equipment (hospital_id, status);

CREATE INDEX IF NOT EXISTS idx_appointments_lookup 
    ON public.appointments (hospital_id, preferred_date, status);

CREATE INDEX IF NOT EXISTS idx_appointments_patient_phone 
    ON public.appointments (patient_phone);


-- <<< END MIGRATION: 009_create_indexes_and_constraints.sql <<<

-- >>> MIGRATION: 010_enable_rls_policies.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 010: Row Level Security (RLS) Policies
-- ==============================================================================
-- Security Model: Zero trust in client claims. Authorization based on validated
-- Supabase auth.uid() and server-assigned roles in public.profiles.
-- ==============================================================================

-- Helper function to check if the caller is an active authority/admin
CREATE OR REPLACE FUNCTION public.is_authority_or_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid()
          AND role IN ('authority', 'platform_admin')
          AND account_status = 'active'
    );
END;
$$;

-- Helper function to get the hospital ID assigned to the current hospital admin
CREATE OR REPLACE FUNCTION public.get_auth_user_hospital_id()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
    h_id INTEGER;
BEGIN
    SELECT hospital_id INTO h_id
    FROM public.profiles
    WHERE id = auth.uid()
      AND role = 'hospital_admin'
      AND account_status = 'active';
    RETURN h_id;
END;
$$;

-- Helper function to check if the caller is a platform administrator
CREATE OR REPLACE FUNCTION public.is_platform_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid()
          AND role = 'platform_admin'
          AND account_status = 'active'
    );
END;
$$;

REVOKE EXECUTE ON FUNCTION public.is_authority_or_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_authority_or_admin() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_hospital_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.get_auth_user_hospital_id() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.is_platform_admin() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.is_platform_admin() TO authenticated, service_role;


-- ──────────────────────────────────────────────────────────────────────────────
-- 1. PROFILES TABLE RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- Users can read their own profile
CREATE POLICY "profiles_read_own" ON public.profiles
    FOR SELECT USING (auth.uid() = id);

-- Authority / platform admins can read all profiles
CREATE POLICY "profiles_read_authority" ON public.profiles
    FOR SELECT USING (public.is_authority_or_admin());

-- Users can update only their non-privileged fields (name, phone)
CREATE POLICY "profiles_update_own" ON public.profiles
    FOR UPDATE USING (auth.uid() = id)
    WITH CHECK (
        auth.uid() = id
        -- Prevent privilege escalation: role and hospital_id cannot be changed by user
        AND role = (SELECT p.role FROM public.profiles p WHERE p.id = auth.uid())
        AND COALESCE(hospital_id, -1) = COALESCE((SELECT p.hospital_id FROM public.profiles p WHERE p.id = auth.uid()), -1)
    );

-- Platform Admin can manage all profiles
CREATE POLICY "profiles_admin_all" ON public.profiles
    FOR ALL USING (public.is_platform_admin());


-- ──────────────────────────────────────────────────────────────────────────────
-- 2. HOSPITALS TABLE RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.hospitals ENABLE ROW LEVEL SECURITY;

-- Public read for hospital directory discovery
CREATE POLICY "hospitals_public_read" ON public.hospitals
    FOR SELECT USING (true);

-- Hospital admins can update only their assigned hospital
CREATE POLICY "hospitals_admin_update_own" ON public.hospitals
    FOR UPDATE USING (id = public.get_auth_user_hospital_id())
    WITH CHECK (id = public.get_auth_user_hospital_id());

-- Authorities and platform admins can insert and update hospitals
CREATE POLICY "hospitals_authority_modify" ON public.hospitals
    FOR ALL USING (public.is_authority_or_admin());


-- ──────────────────────────────────────────────────────────────────────────────
-- 3. HOSPITAL CAPABILITIES RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.hospital_capabilities ENABLE ROW LEVEL SECURITY;

-- Public read for clinical triage discovery
CREATE POLICY "capabilities_public_read" ON public.hospital_capabilities
    FOR SELECT USING (true);

-- Hospital admins can manage capabilities for their assigned facility
CREATE POLICY "capabilities_hospital_admin_manage" ON public.hospital_capabilities
    FOR ALL USING (hospital_id = public.get_auth_user_hospital_id())
    WITH CHECK (hospital_id = public.get_auth_user_hospital_id());

-- Authorities can verify and manage all capabilities
CREATE POLICY "capabilities_authority_manage" ON public.hospital_capabilities
    FOR ALL USING (public.is_authority_or_admin());


-- ──────────────────────────────────────────────────────────────────────────────
-- 4. HOSPITAL CAPACITY & HISTORY RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.hospital_capacity ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_capacity_history ENABLE ROW LEVEL SECURITY;

-- Public read of live capacity for patient matching
CREATE POLICY "capacity_public_read" ON public.hospital_capacity
    FOR SELECT USING (true);

-- Hospital admin can update ONLY their own facility capacity
CREATE POLICY "capacity_hospital_admin_update" ON public.hospital_capacity
    FOR UPDATE USING (hospital_id = public.get_auth_user_hospital_id())
    WITH CHECK (hospital_id = public.get_auth_user_hospital_id());

-- Authorities can manage capacity for mutual aid & regional load-balancing
CREATE POLICY "capacity_authority_manage" ON public.hospital_capacity
    FOR ALL USING (public.is_authority_or_admin());

-- Historical capacity: readable by authorized staff and authorities only
CREATE POLICY "capacity_history_admin_read" ON public.hospital_capacity_history
    FOR SELECT USING (
        hospital_id = public.get_auth_user_hospital_id() 
        OR public.is_authority_or_admin()
    );


-- ──────────────────────────────────────────────────────────────────────────────
-- 5. EMERGENCY REQUESTS (SOS) RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.emergency_requests ENABLE ROW LEVEL SECURITY;

-- Public citizen SOS creation (both authenticated and guest)
CREATE POLICY "emergency_requests_insert_public" ON public.emergency_requests
    FOR INSERT WITH CHECK (true);

-- Authenticated patient can view their own requests
CREATE POLICY "emergency_requests_patient_read" ON public.emergency_requests
    FOR SELECT USING (
        (patient_id IS NOT NULL AND patient_id = auth.uid())
        OR target_hospital_id = public.get_auth_user_hospital_id()
        OR public.is_authority_or_admin()
    );

-- Hospital admins can update requests targeted to their hospital (e.g. acknowledge, mark arrival)
CREATE POLICY "emergency_requests_hospital_admin_update" ON public.emergency_requests
    FOR UPDATE USING (target_hospital_id = public.get_auth_user_hospital_id())
    WITH CHECK (target_hospital_id = public.get_auth_user_hospital_id());

-- Authorities have full oversight of emergency dispatch workflows
CREATE POLICY "emergency_requests_authority_all" ON public.emergency_requests
    FOR ALL USING (public.is_authority_or_admin());


-- ──────────────────────────────────────────────────────────────────────────────
-- 6. EMERGENCY AUDIT EVENTS RLS (Immutable)
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.emergency_request_events ENABLE ROW LEVEL SECURITY;

-- Append-only policy: authenticated users and system can append audit events
CREATE POLICY "emergency_events_insert" ON public.emergency_request_events
    FOR INSERT WITH CHECK (true);

-- Read policy: participants in the request or authorities can read the history
CREATE POLICY "emergency_events_read" ON public.emergency_request_events
    FOR SELECT USING (
        public.is_authority_or_admin()
        OR EXISTS (
            SELECT 1 FROM public.emergency_requests r
            WHERE r.id = emergency_request_events.request_id
              AND (
                  r.patient_id = auth.uid()
                  OR r.target_hospital_id = public.get_auth_user_hospital_id()
              )
        )
    );
-- Notice: NO UPDATE OR DELETE POLICIES CREATED -> Modifications are strictly blocked.


-- ──────────────────────────────────────────────────────────────────────────────
-- 7. HOSPITAL REQUEST RESPONSES RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.hospital_request_responses ENABLE ROW LEVEL SECURITY;

-- Hospital admins manage responses for their assigned hospital
CREATE POLICY "responses_hospital_admin_manage" ON public.hospital_request_responses
    FOR ALL USING (hospital_id = public.get_auth_user_hospital_id())
    WITH CHECK (hospital_id = public.get_auth_user_hospital_id());

-- Patients can view responses dispatched for their emergency request
CREATE POLICY "responses_patient_read" ON public.hospital_request_responses
    FOR SELECT USING (
        EXISTS (
            SELECT 1 FROM public.emergency_requests r
            WHERE r.id = hospital_request_responses.request_id
              AND r.patient_id = auth.uid()
        )
        OR public.is_authority_or_admin()
    );


-- ──────────────────────────────────────────────────────────────────────────────
-- 8. NORMAL HEALTHCARE (DEPARTMENTS, EQUIPMENT, APPOINTMENTS) RLS
-- ──────────────────────────────────────────────────────────────────────────────
ALTER TABLE public.hospital_departments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hospital_equipment ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.appointments ENABLE ROW LEVEL SECURITY;

-- Public read for departments and equipment
CREATE POLICY "departments_public_read" ON public.hospital_departments FOR SELECT USING (true);
CREATE POLICY "equipment_public_read" ON public.hospital_equipment FOR SELECT USING (true);

-- Hospital admin manage their departments & equipment
CREATE POLICY "departments_admin_manage" ON public.hospital_departments
    FOR ALL USING (hospital_id = public.get_auth_user_hospital_id());
CREATE POLICY "equipment_admin_manage" ON public.hospital_equipment
    FOR ALL USING (hospital_id = public.get_auth_user_hospital_id());

-- Appointments: citizen creation & patient read
CREATE POLICY "appointments_insert" ON public.appointments FOR INSERT WITH CHECK (true);
CREATE POLICY "appointments_read" ON public.appointments
    FOR SELECT USING (
        patient_id = auth.uid()
        OR hospital_id = public.get_auth_user_hospital_id()
        OR public.is_authority_or_admin()
    );
CREATE POLICY "appointments_admin_update" ON public.appointments
    FOR UPDATE USING (hospital_id = public.get_auth_user_hospital_id())
    WITH CHECK (hospital_id = public.get_auth_user_hospital_id());


-- <<< END MIGRATION: 010_enable_rls_policies.sql <<<

-- >>> MIGRATION: 011_add_email_to_profiles.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 011: Add Email Column to User Profiles
-- ==============================================================================
-- Description: Adds email column to public.profiles table and indexes it.
-- Enables direct email lookup, duplicate checking, and login verification.
-- ==============================================================================

-- 1. Add email column safely if not exists
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- 2. Create index on email for fast lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email 
ON public.profiles (email) 
WHERE email IS NOT NULL;

-- 3. Backfill email from metadata if metadata contains email
UPDATE public.profiles 
SET email = LOWER(TRIM(metadata->>'email'))
WHERE email IS NULL 
  AND metadata->>'email' IS NOT NULL 
  AND metadata->>'email' != '';

COMMENT ON COLUMN public.profiles.email IS 'User email address synchronized with auth.users for fast profile lookups.';


-- <<< END MIGRATION: 011_add_email_to_profiles.sql <<<

-- >>> MIGRATION: 012_fix_profiles_rls_recursion.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Migration 012: Fix Profiles RLS Recursion & Schema Hardening
-- ==============================================================================
-- Resolves:
-- 1. ERROR 42P17: Infinite recursion detected in policy for relation "profiles"
--    Fix: Functions querying public.profiles must run with:
--         SECURITY DEFINER SET search_path = public, pg_temp SET row_security = off
-- 2. Privilege Escalation Prevention:
--    Fix: Prevent users from updating their own role, hospital_id, or account_status
--         using non-recursive security definer helper functions.
-- 3. ERROR 42703: column "hold_expires_at" does not exist
--    Fix: Explicit ALTER TABLE ADD COLUMN IF NOT EXISTS before index creation
-- 4. ERROR 42703: column "email" does not exist on public.profiles
--    Fix: Explicit ALTER TABLE ADD COLUMN IF NOT EXISTS
-- 5. ERROR 42501: permission denied for schema auth
--    Fix: Never attempt DDL on auth.users; reference native auth.users(id) only
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Step 1: Ensure columns exist before referencing them in indexes or policies
-- ------------------------------------------------------------------------------
ALTER TABLE public.emergency_requests 
ADD COLUMN IF NOT EXISTS hold_expires_at TIMESTAMPTZ;

ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- ------------------------------------------------------------------------------
-- Step 2: Recreate helper functions with row_security = off & secure search_path
-- ------------------------------------------------------------------------------

-- is_authority_or_admin: Checks if the caller is an active authority or admin
CREATE OR REPLACE FUNCTION public.is_authority_or_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid()
          AND role IN ('authority', 'platform_admin')
          AND account_status = 'active'
    );
END;
$$;

-- get_auth_user_hospital_id: Gets the hospital assigned to the caller
CREATE OR REPLACE FUNCTION public.get_auth_user_hospital_id()
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
    h_id INTEGER;
BEGIN
    SELECT hospital_id INTO h_id
    FROM public.profiles
    WHERE id = auth.uid()
      AND role = 'hospital_admin'
      AND account_status = 'active';
    RETURN h_id;
END;
$$;

-- is_platform_admin: Checks if the caller is a platform administrator
CREATE OR REPLACE FUNCTION public.is_platform_admin()
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM public.profiles
        WHERE id = auth.uid()
          AND role = 'platform_admin'
          AND account_status = 'active'
    );
END;
$$;

-- get_auth_user_role: Safely fetches current user's role without recursion
CREATE OR REPLACE FUNCTION public.get_auth_user_role()
RETURNS VARCHAR
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
    r VARCHAR;
BEGIN
    SELECT role INTO r FROM public.profiles WHERE id = auth.uid();
    RETURN r;
END;
$$;

-- get_auth_user_account_status: Safely fetches current user's account_status without recursion
CREATE OR REPLACE FUNCTION public.get_auth_user_account_status()
RETURNS VARCHAR
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public, pg_temp
SET row_security = off
AS $$
DECLARE
    s VARCHAR;
BEGIN
    SELECT account_status INTO s FROM public.profiles WHERE id = auth.uid();
    RETURN s;
END;
$$;

-- Revoke execute from PUBLIC and anon; grant only to authenticated and service_role
REVOKE EXECUTE ON FUNCTION public.is_authority_or_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_authority_or_admin() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_hospital_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_hospital_id() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.is_platform_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_platform_admin() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_role() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_role() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_account_status() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_account_status() TO authenticated, service_role;

-- ------------------------------------------------------------------------------
-- Step 3: Recreate non-recursive, performance-optimized policies on public.profiles
-- ------------------------------------------------------------------------------
DROP POLICY IF EXISTS "profiles_read_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_read_authority" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_admin_all" ON public.profiles;

-- 1. Patients and users can read their own profile
CREATE POLICY "profiles_read_own" ON public.profiles
    FOR SELECT USING ((SELECT auth.uid()) = id);

-- 2. Authority and platform admins can read all profiles
CREATE POLICY "profiles_read_authority" ON public.profiles
    FOR SELECT USING ((SELECT public.is_authority_or_admin()));

-- 3. Users can update only non-privileged fields; role, hospital_id, and account_status are immutable
CREATE POLICY "profiles_update_own" ON public.profiles
    FOR UPDATE USING ((SELECT auth.uid()) = id)
    WITH CHECK (
        (SELECT auth.uid()) = id
        AND role = (SELECT public.get_auth_user_role())
        AND COALESCE(hospital_id, -1) = COALESCE((SELECT public.get_auth_user_hospital_id()), -1)
        AND account_status = (SELECT public.get_auth_user_account_status())
    );

-- 4. Platform administrators retain full management access
CREATE POLICY "profiles_admin_all" ON public.profiles
    FOR ALL USING ((SELECT public.is_platform_admin()))
    WITH CHECK ((SELECT public.is_platform_admin()));

-- ------------------------------------------------------------------------------
-- Step 4: Ensure performance indexes exist
-- ------------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_emergency_hold_expiry 
    ON public.emergency_requests (hold_expires_at) 
    WHERE status IN ('pending', 'acknowledged', 'accepted');

CREATE INDEX IF NOT EXISTS idx_profiles_email 
    ON public.profiles (email) 
    WHERE email IS NOT NULL;

-- <<< END MIGRATION: 012_fix_profiles_rls_recursion.sql <<<

-- >>> SEED: 001_seed_hospitals.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Seed 001: Verified Public Hospitals & Baseline Capacity
-- ==============================================================================
-- Populates the 36 verified public healthcare infrastructure facilities.
-- Note: Capacity values reflect baseline allocations from verified records.
-- ==============================================================================

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (1, 'Victoria Hospital', 'Victoria Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9635, 77.5734, '+91-800-000-8787', '+91-800-000-8787', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (1, 1000, 150, 850, 0, 120, 24, 96, 70, 28, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (2, 'Bowring and Lady Curzon Medical College and Research Institute', 'Bowring and Lady Curzon Medical College and Research Institute, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9784, 77.6035, '+91-800-000-3705', '+91-800-000-3705', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (2, 686, 102, 584, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (3, 'ESIC Medical College and Hospital Rajajinagar', 'ESIC Medical College and Hospital Rajajinagar, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9916, 77.5556, '+91-800-000-5342', '+91-800-000-5342', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (3, 1100, 165, 935, 0, 150, 30, 120, 90, 36, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (4, 'KC General Hospital', 'KC General Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 13.0067, 77.569, '+91-800-000-9645', '+91-800-000-9645', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (4, 650, 97, 553, 0, 85, 17, 68, 50, 20, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (5, 'Minto Ophthalmic Hospital', 'Minto Ophthalmic Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9647, 77.5748, '+91-800-000-7932', '+91-800-000-7932', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (5, 300, 45, 255, 0, 30, 6, 24, 15, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (6, 'Indira Gandhi Institute of Child Health', 'Indira Gandhi Institute of Child Health, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9507, 77.5848, '+91-800-000-4470', '+91-800-000-4470', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (6, 500, 75, 425, 0, 70, 14, 56, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (7, 'Vani Vilas Women and Children Hospital', 'Vani Vilas Women and Children Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 12.9638, 77.5729, '+91-800-000-9835', '+91-800-000-9835', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (7, 600, 90, 510, 0, 80, 16, 64, 40, 16, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (8, 'Yelahanka Government Hospital', 'Yelahanka Government Hospital, Bengaluru', 'Bengaluru', 'Bengaluru Urban', 'Karnataka', 13.1007, 77.5963, '+91-800-000-4295', '+91-800-000-4295', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (8, 300, 45, 255, 0, 35, 7, 28, 20, 8, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (9, 'Anekal Taluk Government Hospital', 'Anekal Taluk Government Hospital, Anekal', 'Anekal', 'Bengaluru Urban', 'Karnataka', 12.7083, 77.6957, '+91-800-000-6107', '+91-800-000-6107', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (9, 250, 37, 213, 0, 30, 6, 24, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (10, 'Devanahalli Taluk Hospital', 'Devanahalli Taluk Hospital, Devanahalli', 'Devanahalli', 'Bengaluru Rural', 'Karnataka', 13.2433, 77.7131, '+91-800-000-7537', '+91-800-000-7537', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (10, 200, 30, 170, 0, 25, 5, 20, 15, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (11, 'Nelamangala Taluk Hospital', 'Nelamangala Taluk Hospital, Nelamangala', 'Nelamangala', 'Bengaluru Rural', 'Karnataka', 13.0972, 77.3891, '+91-800-000-7118', '+91-800-000-7118', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (11, 220, 33, 187, 0, 28, 5, 23, 16, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (12, 'KR Hospital Mysuru', 'KR Hospital Mysuru, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3072, 76.65, '+91-800-000-8177', '+91-800-000-8177', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (12, 1050, 157, 893, 0, 140, 28, 112, 80, 32, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (13, 'KIMS Mysuru', 'KIMS Mysuru, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.2958, 76.6394, '+91-800-000-9479', '+91-800-000-9479', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (13, 1200, 180, 1020, 0, 150, 30, 120, 85, 34, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (14, 'Cheluvamba Hospital for Women and Children', 'Cheluvamba Hospital for Women and Children, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3065, 76.6495, '+91-800-000-8397', '+91-800-000-8397', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (14, 450, 67, 383, 0, 60, 12, 48, 30, 12, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (15, 'Mysuru District Hospital', 'Mysuru District Hospital, Mysuru', 'Mysuru', 'Mysuru', 'Karnataka', 12.3141, 76.652, '+91-800-000-2982', '+91-800-000-2982', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (15, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (16, 'Nanjangud Taluk Hospital', 'Nanjangud Taluk Hospital, Nanjangud', 'Nanjangud', 'Mysuru', 'Karnataka', 12.12, 76.683, '+91-800-000-5061', '+91-800-000-5061', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (16, 250, 37, 213, 0, 30, 6, 24, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (17, 'Belagavi Institute of Medical Sciences', 'Belagavi Institute of Medical Sciences, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.8497, 74.4977, '+91-800-000-4681', '+91-800-000-4681', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (17, 750, 112, 638, 0, 95, 19, 76, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (18, 'District Hospital Belagavi', 'District Hospital Belagavi, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.8528, 74.504, '+91-800-000-2049', '+91-800-000-2049', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (18, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (19, 'ESIC Hospital Udyambag', 'ESIC Hospital Udyambag, Belagavi', 'Belagavi', 'Belagavi', 'Karnataka', 15.885, 74.531, '+91-800-000-6539', '+91-800-000-6539', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (19, 300, 45, 255, 0, 40, 8, 32, 22, 8, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (20, 'Gokak Taluk Hospital', 'Gokak Taluk Hospital, Gokak', 'Gokak', 'Belagavi', 'Karnataka', 16.169, 74.823, '+91-800-000-1344', '+91-800-000-1344', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (20, 220, 33, 187, 0, 28, 5, 23, 16, 6, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (21, 'KIMS Hubballi', 'KIMS Hubballi, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.3647, 75.1239, '+91-800-000-4770', '+91-800-000-4770', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (21, 1400, 210, 1190, 0, 180, 36, 144, 110, 44, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (22, 'Dharwad District Hospital', 'Dharwad District Hospital, Dharwad', 'Dharwad', 'Dharwad', 'Karnataka', 15.4589, 75.0078, '+91-800-000-4608', '+91-800-000-4608', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (22, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (23, 'ESIC Hospital Hubballi', 'ESIC Hospital Hubballi, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.3605, 75.125, '+91-800-000-1117', '+91-800-000-1117', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (23, 350, 52, 298, 0, 45, 9, 36, 25, 10, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (24, 'Kittur Rani Channamma Taluk Hospital', 'Kittur Rani Channamma Taluk Hospital, Hubballi', 'Hubballi', 'Dharwad', 'Karnataka', 15.349, 75.138, '+91-800-000-2163', '+91-800-000-2163', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (24, 250, 37, 213, 0, 32, 6, 26, 18, 7, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (25, 'Wenlock District Hospital', 'Wenlock District Hospital, Mangaluru', 'Mangaluru', 'Dakshina Kannada', 'Karnataka', 12.8705, 74.843, '+91-800-000-1964', '+91-800-000-1964', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (25, 1000, 150, 850, 0, 130, 26, 104, 75, 30, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (26, 'Govt Lady Goschen Hospital', 'Govt Lady Goschen Hospital, Mangaluru', 'Mangaluru', 'Dakshina Kannada', 'Karnataka', 12.8719, 74.8425, '+91-800-000-4750', '+91-800-000-4750', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (26, 400, 60, 340, 0, 55, 11, 44, 28, 11, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (27, 'Gulbarga Institute of Medical Sciences', 'Gulbarga Institute of Medical Sciences, Kalaburagi', 'Kalaburagi', 'Kalaburagi', 'Karnataka', 17.3297, 76.8343, '+91-800-000-2104', '+91-800-000-2104', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (27, 750, 112, 638, 0, 95, 19, 76, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (28, 'Kalaburagi District Hospital', 'Kalaburagi District Hospital, Kalaburagi', 'Kalaburagi', 'Kalaburagi', 'Karnataka', 17.3358, 76.8376, '+91-800-000-1514', '+91-800-000-1514', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (28, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (29, 'Chigateri General Hospital', 'Chigateri General Hospital, Davanagere', 'Davanagere', 'Davanagere', 'Karnataka', 14.4661, 75.9186, '+91-800-000-6413', '+91-800-000-6413', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (29, 650, 97, 553, 0, 85, 17, 68, 50, 20, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (30, 'Davanagere District Hospital', 'Davanagere District Hospital, Davanagere', 'Davanagere', 'Davanagere', 'Karnataka', 14.4644, 75.9218, '+91-800-000-2160', '+91-800-000-2160', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (30, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (31, 'VIMS Ballari', 'VIMS Ballari, Ballari', 'Ballari', 'Ballari', 'Karnataka', 15.1394, 76.9214, '+91-800-000-9423', '+91-800-000-9423', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (31, 750, 112, 638, 0, 100, 20, 80, 60, 24, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (32, 'Ballari District Hospital', 'Ballari District Hospital, Ballari', 'Ballari', 'Ballari', 'Karnataka', 15.149, 76.933, '+91-800-000-4899', '+91-800-000-4899', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (32, 500, 75, 425, 0, 65, 13, 52, 35, 14, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (33, 'Tumakuru District Hospital', 'Tumakuru District Hospital, Tumakuru', 'Tumakuru', 'Tumakuru', 'Karnataka', 13.3379, 77.1173, '+91-800-000-5562', '+91-800-000-5562', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (33, 600, 90, 510, 0, 80, 16, 64, 45, 18, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (34, 'Tumakuru Medical College Hospital', 'Tumakuru Medical College Hospital, Tumakuru', 'Tumakuru', 'Tumakuru', 'Karnataka', 13.3422, 77.101, '+91-800-000-8953', '+91-800-000-8953', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (34, 900, 135, 765, 0, 120, 24, 96, 70, 28, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (35, 'Shivamogga Institute of Medical Sciences', 'Shivamogga Institute of Medical Sciences, Shivamogga', 'Shivamogga', 'Shivamogga', 'Karnataka', 13.9299, 75.5681, '+91-800-000-4510', '+91-800-000-4510', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (35, 700, 105, 595, 0, 90, 18, 72, 55, 22, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

INSERT INTO public.hospitals (id, name, address, city, district, state, latitude, longitude, contact_number, emergency_phone, verification_status, operational_status)
VALUES (36, 'McGann District Hospital', 'McGann District Hospital, Shivamogga', 'Shivamogga', 'Shivamogga', 'Karnataka', 13.9325, 75.5669, '+91-800-000-9834', '+91-800-000-9834', 'verified', 'operational')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    district = EXCLUDED.district,
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude;

INSERT INTO public.hospital_capacity (hospital_id, total_beds, available_beds, occupied_beds, provisionally_allocated_beds, icu_total, icu_available, icu_occupied, ventilators_total, ventilators_available, oxygen_status, emergency_receiving_status, status)
VALUES (36, 550, 82, 468, 0, 70, 14, 56, 40, 16, 'adequate', 'available', 'available')
ON CONFLICT (hospital_id) DO UPDATE SET
    total_beds = EXCLUDED.total_beds,
    available_beds = EXCLUDED.available_beds,
    occupied_beds = EXCLUDED.occupied_beds,
    icu_total = EXCLUDED.icu_total,
    icu_available = EXCLUDED.icu_available,
    icu_occupied = EXCLUDED.icu_occupied;

-- <<< END SEED: 001_seed_hospitals.sql <<<

-- >>> SEED: 002_seed_capabilities_and_departments.sql >>>
-- ==============================================================================
-- AIIS Backend V2 – Seed 002: Baseline Capabilities & Department Readiness
-- ==============================================================================
-- Seeds clinical capability baselines and departments for monitored facilities.
-- Note: Capabilities default to 'verified' for tertiary medical colleges, 'unknown' for secondary.
-- ==============================================================================

-- 1. Capabilities for Top Core Facilities (e.g. Victoria Hospital id=1, Bowring id=2, KC General id=4)
INSERT INTO public.hospital_capabilities (hospital_id, capability_name, verification_state, details)
VALUES 
    (1, 'emergency_receiving', 'verified', '{"bay_count": 24, "triage_available": true}'::jsonb),
    (1, 'icu', 'verified', '{"level": "Level 3 Tertiary", "dedicated_intensivists": true}'::jsonb),
    (1, 'trauma', 'verified', '{"trauma_level": "Level 1 Apex", "ot_ready_24_7": true}'::jsonb),
    (1, 'cardiac', 'verified', '{"cath_lab": true, "coronary_care_unit": true}'::jsonb),
    (1, 'stroke_neuro', 'verified', '{"ct_scanner_24_7": true, "thrombolysis_ready": true}'::jsonb),
    (1, 'paediatric', 'verified', '{"picu_beds": 18, "nicu_beds": 12}'::jsonb),
    (1, 'respiratory_emergencies', 'verified', '{"piped_o2": true, "high_flow_nasal": true}'::jsonb),

    (2, 'emergency_receiving', 'verified', '{"bay_count": 16, "triage_available": true}'::jsonb),
    (2, 'icu', 'verified', '{"level": "Level 2 Secondary", "dedicated_intensivists": true}'::jsonb),
    (2, 'cardiac', 'verified', '{"cath_lab": true}'::jsonb),
    (2, 'trauma', 'verified', '{"trauma_bay": true}'::jsonb),

    (4, 'emergency_receiving', 'verified', '{"bay_count": 12, "triage_available": true}'::jsonb),
    (4, 'respiratory_emergencies', 'verified', '{"o2_beds": 40}'::jsonb)
ON CONFLICT (hospital_id, capability_name) DO UPDATE SET
    verification_state = EXCLUDED.verification_state,
    details = EXCLUDED.details;

-- 2. Departments for Core Facilities
INSERT INTO public.hospital_departments (hospital_id, name, status, doctors_on_duty, notes)
VALUES
    (1, 'Emergency & Casualty', 'Ready', 8, 'Full multi-specialty coverage'),
    (1, 'Intensive Care Unit (ICU)', 'Ready', 5, 'Level 3 critical care'),
    (1, 'Cardiology', 'Ready', 4, 'Cath lab on standby'),
    (1, 'Radiology & Imaging', 'Ready', 3, 'CT and MRI operational'),
    (1, 'Paediatrics', 'Ready', 4, 'PICU and NICU active'),

    (2, 'Emergency & Casualty', 'Ready', 6, 'Casualty triage operational'),
    (2, 'Intensive Care Unit (ICU)', 'Ready', 3, 'High occupancy'),
    (2, 'General Medicine', 'Ready', 5, 'OPD and inpatient ready'),

    (4, 'Emergency & Casualty', 'Ready', 4, 'Secondary triage ready'),
    (4, 'General Medicine', 'Ready', 4, 'Active')
ON CONFLICT (hospital_id, name) DO UPDATE SET
    status = EXCLUDED.status,
    doctors_on_duty = EXCLUDED.doctors_on_duty;

-- 3. Diagnostic and Life-Support Equipment
INSERT INTO public.hospital_equipment (hospital_id, name, status, total_units, available_units)
VALUES
    (1, 'CT Scanner', 'Available', 2, 2),
    (1, 'MRI Scanner', 'Available', 1, 1),
    (1, 'Ventilators', 'Available', 70, 28),
    (1, 'Hemodialysis', 'Available', 12, 4),
    
    (2, 'CT Scanner', 'Available', 1, 1),
    (2, 'Ventilators', 'Available', 45, 18),
    
    (4, 'X-Ray Machine', 'Available', 2, 2),
    (4, 'Ventilators', 'Available', 20, 8)
ON CONFLICT (hospital_id, name) DO UPDATE SET
    status = EXCLUDED.status,
    available_units = EXCLUDED.available_units;


-- <<< END SEED: 002_seed_capabilities_and_departments.sql <<<

