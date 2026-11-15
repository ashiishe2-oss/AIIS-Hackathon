-- ==============================================================================
-- AIIS Backend V2 – Migration 011: Add Email Column to User Profiles
-- ==============================================================================
-- Description: Adds email column to public.profiles table and indexes it.
-- Enables direct email lookup, duplicate checking, and login verification.
-- ==============================================================================

-- 1. Add email column safely if not exists
ALTER TABLE public.profiles 
ADD COLUMN IF NOT EXISTS email VARCHAR(255);

-- 2. Create index on email for fast lookups
CREATE INDEX IF NOT EXISTS idx_profiles_email 
ON public.profiles (email) 
WHERE email IS NOT NULL;

-- 3. Backfill email from metadata if metadata contains email
UPDATE public.profiles 
SET email = LOWER(TRIM(metadata->>'email'))
WHERE email IS NULL 
  AND metadata->>'email' IS NOT NULL 
  AND metadata->>'email' != '';

COMMENT ON COLUMN public.profiles.email IS 'User email address synchronized with auth.users for fast profile lookups.';

