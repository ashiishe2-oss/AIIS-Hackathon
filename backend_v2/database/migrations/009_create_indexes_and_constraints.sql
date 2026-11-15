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

