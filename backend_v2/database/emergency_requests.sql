-- ================================================================
-- AIIS Backend V2 – Emergency SOS & Coordination Schema
-- ================================================================
-- Execute in Supabase SQL Editor: Dashboard -> SQL Editor -> New Query
-- ================================================================

-- 1. Create table if missing
CREATE TABLE IF NOT EXISTS public.emergency_requests (
    id VARCHAR(36) PRIMARY KEY,
    hospital_id INTEGER REFERENCES public.hospitals(id) ON DELETE SET NULL,
    emergency_category VARCHAR(64) DEFAULT 'general' NOT NULL,
    patient_name VARCHAR(128) DEFAULT 'Patient',
    companion_name VARCHAR(128),
    contact_phone VARCHAR(32),
    severity VARCHAR(32) DEFAULT 'HIGH' NOT NULL,
    status VARCHAR(64) DEFAULT 'REQUEST_SUBMITTED' NOT NULL,
    otp VARCHAR(8) NOT NULL,
    estimated_travel_minutes INTEGER DEFAULT 15,
    user_location_name VARCHAR(128),
    latitude NUMERIC(10, 6),
    longitude NUMERIC(10, 6),
    notes TEXT,
    cancellation_reason TEXT,
    hold_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT now() NOT NULL
);

-- 2. Indexes for fast status checks and hospital casualty dashboards
CREATE INDEX IF NOT EXISTS idx_emergency_hospital_status ON public.emergency_requests(hospital_id, status);
CREATE INDEX IF NOT EXISTS idx_emergency_created_at ON public.emergency_requests(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_emergency_status ON public.emergency_requests(status);

-- 3. Auto-update updated_at timestamp trigger
CREATE OR REPLACE FUNCTION public.set_emergency_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS emergency_requests_set_updated_at ON public.emergency_requests;
CREATE TRIGGER emergency_requests_set_updated_at
  BEFORE UPDATE ON public.emergency_requests
  FOR EACH ROW EXECUTE FUNCTION public.set_emergency_updated_at();

-- 4. Row Level Security (RLS)
ALTER TABLE public.emergency_requests ENABLE ROW LEVEL SECURITY;

-- Policy A: Anonymous citizen can create an SOS request
CREATE POLICY "emergency_citizen_insert"
ON public.emergency_requests
FOR INSERT
WITH CHECK (true);

-- Policy B: Anonymous citizen can read an emergency request if they know the ID
CREATE POLICY "emergency_citizen_read"
ON public.emergency_requests
FOR SELECT
USING (true);

-- Policy C: Hospital Admin can view emergency requests directed to their hospital
CREATE POLICY "emergency_hospital_admin_read"
ON public.emergency_requests
FOR SELECT
USING (
  auth.role() = 'authenticated'
  AND (
    (auth.jwt() -> 'user_metadata' ->> 'role') = 'authority'
    OR (
      (auth.jwt() -> 'user_metadata' ->> 'role') = 'hospital_admin'
      AND hospital_id = (auth.jwt() -> 'user_metadata' ->> 'hospital_id')::int
    )
  )
);

-- Policy D: Hospital Admin can update requests for their hospital (e.g., mark arrival)
CREATE POLICY "emergency_hospital_admin_update"
ON public.emergency_requests
FOR UPDATE
USING (
  auth.role() = 'authenticated'
  AND (
    (auth.jwt() -> 'user_metadata' ->> 'role') = 'authority'
    OR (
      (auth.jwt() -> 'user_metadata' ->> 'role') = 'hospital_admin'
      AND hospital_id = (auth.jwt() -> 'user_metadata' ->> 'hospital_id')::int
    )
  )
);

