-- ==============================================================================
-- AIIS Backend V2 – Migration 008: Normal Healthcare Entities
-- ==============================================================================
-- Description: Department readiness, diagnostic equipment, and outpatient appointments.
-- Supported by frontend: #/hospital (Staff readiness) & #/planned (Appointments).
-- ==============================================================================

-- 1. Hospital Departments & Operational Readiness
CREATE TABLE IF NOT EXISTS public.hospital_departments (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Ready' 
        CHECK (status IN ('Ready', 'Limited', 'Closed')),
    doctors_on_duty INTEGER DEFAULT 1 CHECK (doctors_on_duty >= 0),
    notes TEXT,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_hospital_department UNIQUE (hospital_id, name)
);

-- 2. Hospital Diagnostic & Clinical Equipment Availability
CREATE TABLE IF NOT EXISTS public.hospital_equipment (
    id SERIAL PRIMARY KEY,
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'Available' 
        CHECK (status IN ('Available', 'Limited', 'Not available')),
    total_units INTEGER DEFAULT 1 CHECK (total_units >= 0),
    available_units INTEGER DEFAULT 1 CHECK (available_units >= 0),
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    CONSTRAINT uq_hospital_equipment UNIQUE (hospital_id, name),
    CONSTRAINT chk_equipment_units CHECK (available_units <= total_units)
);

-- 3. Outpatient Consultation Appointments
CREATE TABLE IF NOT EXISTS public.appointments (
    id VARCHAR(36) PRIMARY KEY, -- e.g. APT-XXXXXX
    hospital_id INTEGER NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID REFERENCES public.profiles(id) ON DELETE SET NULL,
    patient_name VARCHAR(128) NOT NULL,
    patient_phone VARCHAR(32) NOT NULL,
    patient_age VARCHAR(16),
    specialty VARCHAR(128) NOT NULL,
    preferred_date DATE NOT NULL,
    preferred_time_slot VARCHAR(64) NOT NULL,
    notes TEXT,
    status VARCHAR(32) NOT NULL DEFAULT 'REQUESTED' 
        CHECK (status IN ('REQUESTED', 'CONFIRMED', 'CANCELLED', 'COMPLETED')),
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- Triggers for updated_at
DROP TRIGGER IF EXISTS trg_hospital_departments_updated_at ON public.hospital_departments;
CREATE TRIGGER trg_hospital_departments_updated_at
    BEFORE UPDATE ON public.hospital_departments
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

DROP TRIGGER IF EXISTS trg_hospital_equipment_updated_at ON public.hospital_equipment;
CREATE TRIGGER trg_hospital_equipment_updated_at
    BEFORE UPDATE ON public.hospital_equipment
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

DROP TRIGGER IF EXISTS trg_appointments_updated_at ON public.appointments;
CREATE TRIGGER trg_appointments_updated_at
    BEFORE UPDATE ON public.appointments
    FOR EACH ROW EXECUTE FUNCTION public.set_current_timestamp_updated_at();

COMMENT ON TABLE public.hospital_departments IS 'Departmental operational readiness published by casualty/hospital staff.';
COMMENT ON TABLE public.hospital_equipment IS 'Key life-support and diagnostic equipment availability.';
COMMENT ON TABLE public.appointments IS 'Citizen-scheduled OPD and specialty consultations.';

