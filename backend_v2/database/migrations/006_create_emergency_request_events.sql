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

