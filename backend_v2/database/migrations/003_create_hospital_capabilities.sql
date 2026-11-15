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

