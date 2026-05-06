import '@testing-library/jest-dom/vitest'

// Provide harmless placeholders so modules that call `createClient()` at import
// time (lib/supabase.ts) don't crash during test collection. Tests that
// exercise realtime explicitly mock the supabase module.
process.env.NEXT_PUBLIC_SUPABASE_URL ??= 'https://test.supabase.invalid'
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??= 'test-anon-key'
