-- ============================================================
-- Calendar source writability
-- ============================================================
-- Date: 2026-06-16
-- Purpose: Track whether the connected user can create events on each calendar
--          source, and forbid a read-only calendar from being the write
--          calendar. Read-only calendars (subscribed / imported / holiday, or
--          shared-as-reader) are valid BUSY sources but cannot have events
--          created on them — choosing one as the write calendar made
--          finalization fail with a provider 403 (requiredAccessLevel).
--
--   1. Add calendar_sources.is_writable (default true; existing rows are
--      assumed writable until the account is re-synced/re-connected, which
--      repopulates the real value from the provider's access role).
--   2. Unstick known read-only Google calendars: mark them non-writable and
--      clear any stale write-calendar designation on them.
--   3. Enforce: a non-writable calendar can never be the write calendar.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260616000001_calendar_source_writable.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

-- 1. New column.
ALTER TABLE "public"."calendar_sources"
    ADD COLUMN IF NOT EXISTS "is_writable" boolean DEFAULT true NOT NULL;

-- 2. Mark known read-only Google calendars non-writable and drop any stale
--    write-calendar designation on them. Imported and holiday calendars are
--    always read-only; other read-only calendars (e.g. shared-as-reader) get
--    corrected the next time the owning account is re-connected.
UPDATE "public"."calendar_sources"
SET "is_writable" = false,
    "is_write_calendar" = false
WHERE "calendar_id" LIKE '%@import.calendar.google.com'
   OR "calendar_id" LIKE '%holiday@group.v.calendar.google.com';

-- 3. A non-writable calendar can never be the write calendar.
ALTER TABLE "public"."calendar_sources"
    DROP CONSTRAINT IF EXISTS "calendar_sources_write_requires_writable";
ALTER TABLE "public"."calendar_sources"
    ADD CONSTRAINT "calendar_sources_write_requires_writable"
    CHECK ("is_writable" OR NOT "is_write_calendar");

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Column present (expect 1 row):
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'calendar_sources' AND column_name = 'is_writable';
-- -- No read-only calendar is a write calendar (expect 0 rows):
-- SELECT id, calendar_id FROM calendar_sources WHERE is_write_calendar AND NOT is_writable;
-- -- Constraint present (expect 1 row):
-- SELECT conname FROM pg_constraint WHERE conname = 'calendar_sources_write_requires_writable';
