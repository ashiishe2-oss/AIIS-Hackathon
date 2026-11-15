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

