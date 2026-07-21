import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || "";
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || "";

// Detect if Supabase has been actively configured by checking url validity
const isConfigured = 
  supabaseUrl && 
  supabaseAnonKey && 
  !supabaseUrl.includes("your-supabase-project") &&
  !supabaseAnonKey.includes("your-supabase-anon-key");

export const supabase = isConfigured 
  ? createClient(supabaseUrl, supabaseAnonKey) 
  : null;

export const isSupabaseEnabled = () => {
  return isConfigured;
};
