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
-- 3. ERROR 23514: emergency_requests_status_check constraint mismatch
--    Fix: Update check constraint to accept both legacy and canonical application states:
--         ('pending', 'acknowledged', 'accepted', 'declined', 'expired', 'cancelled', 'completed',
--          'REQUEST_SUBMITTED', 'HOSPITAL_ACCEPTED', 'PATIENT_ARRIVED', 'CANCELLED', 'EXPIRED')
-- 4. Expiry Partial Index Predicate Alignment:
--    Fix: Index active hold records with ('pending', 'acknowledged', 'accepted', 'REQUEST_SUBMITTED', 'HOSPITAL_ACCEPTED')
-- 5. Complete Policy Inventory & Dropping:
--    Fix: Dynamically drop every policy on public.profiles via pg_policies DO block
-- 6. Table RLS Configuration:
--    Fix: Ensure NO FORCE ROW LEVEL SECURITY so security-definer helper functions can bypass RLS
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- Step 1: Ensure columns, table RLS configuration, and check constraints
-- ------------------------------------------------------------------------------
ALTER TABLE public.emergency_requests 
ADD COLUMN IF NOT EXISTS hold_expires_at TIMESTAMPTZ;

ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- Ensure profiles table has RLS enabled but does NOT force RLS on superuser/table owner
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.profiles NO FORCE ROW LEVEL SECURITY;

-- Harmonize emergency_requests status check constraint
ALTER TABLE public.emergency_requests 
DROP CONSTRAINT IF EXISTS emergency_requests_status_check;

ALTER TABLE public.emergency_requests 
ADD CONSTRAINT emergency_requests_status_check 
CHECK (status IN (
    'pending',
    'acknowledged',
    'accepted',
    'declined',
    'expired',
    'cancelled',
    'completed',
    'REQUEST_SUBMITTED',
    'HOSPITAL_ACCEPTED',
    'PATIENT_ARRIVED',
    'CANCELLED',
    'EXPIRED'
));

-- ------------------------------------------------------------------------------
-- Step 2: Recreate helper functions with row_security = off & secure search_path
-- ------------------------------------------------------------------------------

-- is_authority_or_admin: Checks if the caller is an active authority or platform admin
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

-- get_auth_user_hospital_id: Gets the hospital assigned to an active hospital admin
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

-- get_auth_user_assigned_hospital_id: Gets the hospital_id currently stored for the caller (any role/status)
CREATE OR REPLACE FUNCTION public.get_auth_user_assigned_hospital_id()
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
    WHERE id = auth.uid();
    RETURN h_id;
END;
$$;

-- is_platform_admin: Checks if the caller is an active platform administrator
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

REVOKE EXECUTE ON FUNCTION public.get_auth_user_assigned_hospital_id() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_assigned_hospital_id() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.is_platform_admin() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.is_platform_admin() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_role() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_role() TO authenticated, service_role;

REVOKE EXECUTE ON FUNCTION public.get_auth_user_account_status() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.get_auth_user_account_status() TO authenticated, service_role;

-- ------------------------------------------------------------------------------
-- Step 3: Recreate non-recursive, performance-optimized policies on public.profiles
-- ------------------------------------------------------------------------------

-- Dynamically drop all existing policies on public.profiles to guarantee no zombie or recursive policy remains
DO $$
DECLARE
    pol RECORD;
BEGIN
    FOR pol IN
        SELECT policyname
        FROM pg_policies
        WHERE schemaname = 'public' AND tablename = 'profiles'
    LOOP
        EXECUTE format('DROP POLICY IF EXISTS %I ON public.profiles;', pol.policyname);
    END LOOP;
END;
$$;

-- Also explicitly drop standard names for idempotency
DROP POLICY IF EXISTS "profiles_read_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_read_authority" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_admin_all" ON public.profiles;

-- 1. Patients and users can read their own profile (cached scalar subquery)
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
        AND COALESCE(hospital_id, -1) = COALESCE((SELECT public.get_auth_user_assigned_hospital_id()), -1)
        AND account_status = (SELECT public.get_auth_user_account_status())
    );

-- 4. Platform administrators retain full management access
CREATE POLICY "profiles_admin_all" ON public.profiles
    FOR ALL USING ((SELECT public.is_platform_admin()))
    WITH CHECK ((SELECT public.is_platform_admin()));

-- ------------------------------------------------------------------------------
-- Step 4: Ensure performance indexes exist with correct active status predicate
-- ------------------------------------------------------------------------------
DROP INDEX IF EXISTS public.idx_emergency_hold_expiry;

CREATE INDEX idx_emergency_hold_expiry 
    ON public.emergency_requests (hold_expires_at) 
    WHERE status IN ('pending', 'acknowledged', 'accepted', 'REQUEST_SUBMITTED', 'HOSPITAL_ACCEPTED');

CREATE INDEX IF NOT EXISTS idx_profiles_email 
    ON public.profiles (email) 
    WHERE email IS NOT NULL;

