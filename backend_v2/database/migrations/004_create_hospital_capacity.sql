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

