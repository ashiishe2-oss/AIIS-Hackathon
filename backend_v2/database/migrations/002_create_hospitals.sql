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

