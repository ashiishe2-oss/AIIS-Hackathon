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

