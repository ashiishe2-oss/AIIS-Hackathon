-- ==============================================================================
-- AIIS Backend V2 – Seed 002: Baseline Capabilities & Department Readiness
-- ==============================================================================
-- Seeds clinical capability baselines and departments for monitored facilities.
-- Note: Capabilities default to 'verified' for tertiary medical colleges, 'unknown' for secondary.
-- ==============================================================================

-- 1. Capabilities for Top Core Facilities (e.g. Victoria Hospital id=1, Bowring id=2, KC General id=4)
INSERT INTO public.hospital_capabilities (hospital_id, capability_name, verification_state, details)
VALUES 
    (1, 'emergency_receiving', 'verified', '{"bay_count": 24, "triage_available": true}'::jsonb),
    (1, 'icu', 'verified', '{"level": "Level 3 Tertiary", "dedicated_intensivists": true}'::jsonb),
    (1, 'trauma', 'verified', '{"trauma_level": "Level 1 Apex", "ot_ready_24_7": true}'::jsonb),
    (1, 'cardiac', 'verified', '{"cath_lab": true, "coronary_care_unit": true}'::jsonb),
    (1, 'stroke_neuro', 'verified', '{"ct_scanner_24_7": true, "thrombolysis_ready": true}'::jsonb),
    (1, 'paediatric', 'verified', '{"picu_beds": 18, "nicu_beds": 12}'::jsonb),
    (1, 'respiratory_emergencies', 'verified', '{"piped_o2": true, "high_flow_nasal": true}'::jsonb),

    (2, 'emergency_receiving', 'verified', '{"bay_count": 16, "triage_available": true}'::jsonb),
    (2, 'icu', 'verified', '{"level": "Level 2 Secondary", "dedicated_intensivists": true}'::jsonb),
    (2, 'cardiac', 'verified', '{"cath_lab": true}'::jsonb),
    (2, 'trauma', 'verified', '{"trauma_bay": true}'::jsonb),

    (4, 'emergency_receiving', 'verified', '{"bay_count": 12, "triage_available": true}'::jsonb),
    (4, 'respiratory_emergencies', 'verified', '{"o2_beds": 40}'::jsonb)
ON CONFLICT (hospital_id, capability_name) DO UPDATE SET
    verification_state = EXCLUDED.verification_state,
    details = EXCLUDED.details;

-- 2. Departments for Core Facilities
INSERT INTO public.hospital_departments (hospital_id, name, status, doctors_on_duty, notes)
VALUES
    (1, 'Emergency & Casualty', 'Ready', 8, 'Full multi-specialty coverage'),
    (1, 'Intensive Care Unit (ICU)', 'Ready', 5, 'Level 3 critical care'),
    (1, 'Cardiology', 'Ready', 4, 'Cath lab on standby'),
    (1, 'Radiology & Imaging', 'Ready', 3, 'CT and MRI operational'),
    (1, 'Paediatrics', 'Ready', 4, 'PICU and NICU active'),

    (2, 'Emergency & Casualty', 'Ready', 6, 'Casualty triage operational'),
    (2, 'Intensive Care Unit (ICU)', 'Ready', 3, 'High occupancy'),
    (2, 'General Medicine', 'Ready', 5, 'OPD and inpatient ready'),

    (4, 'Emergency & Casualty', 'Ready', 4, 'Secondary triage ready'),
    (4, 'General Medicine', 'Ready', 4, 'Active')
ON CONFLICT (hospital_id, name) DO UPDATE SET
    status = EXCLUDED.status,
    doctors_on_duty = EXCLUDED.doctors_on_duty;

-- 3. Diagnostic and Life-Support Equipment
INSERT INTO public.hospital_equipment (hospital_id, name, status, total_units, available_units)
VALUES
    (1, 'CT Scanner', 'Available', 2, 2),
    (1, 'MRI Scanner', 'Available', 1, 1),
    (1, 'Ventilators', 'Available', 70, 28),
    (1, 'Hemodialysis', 'Available', 12, 4),
    
    (2, 'CT Scanner', 'Available', 1, 1),
    (2, 'Ventilators', 'Available', 45, 18),
    
    (4, 'X-Ray Machine', 'Available', 2, 2),
    (4, 'Ventilators', 'Available', 20, 8)
ON CONFLICT (hospital_id, name) DO UPDATE SET
    status = EXCLUDED.status,
    available_units = EXCLUDED.available_units;

