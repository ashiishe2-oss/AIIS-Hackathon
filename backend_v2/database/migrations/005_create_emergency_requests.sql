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

