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

