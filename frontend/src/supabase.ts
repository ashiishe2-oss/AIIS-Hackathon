// src/supabase.ts — Complete fixed file
import { createClient, type SupabaseClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.SUPABASE_URL
const supabaseKey = process.env.SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseKey) {
    throw new Error(
        '[AIIS] Missing SUPABASE_URL or SUPABASE_ANON_KEY.\n' +
        'Copy .env.example to .env and fill in your Supabase credentials.'
    )
}

export const supabase: SupabaseClient = createClient(supabaseUrl, supabaseKey)
export default supabase