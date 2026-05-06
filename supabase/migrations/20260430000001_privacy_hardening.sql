-- ============================================================
-- Privacy Hardening — Phase 1
-- ============================================================
-- Date: 2026-04-30
-- Purpose: Close anonymous-read RLS holes and prepare schema
--          for user-driven account deletion.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260430000001_privacy_hardening.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. Drop the six anonymous SELECT policies on public tables.
--    These allowed any visitor with the anon key to read
--    every user's busy slots, events, participants, preferred
--    slots, notes, and notifications.
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "anon can select busy_slots"          ON "public"."busy_slots";
DROP POLICY IF EXISTS "anon can select event_participants"  ON "public"."event_participants";
DROP POLICY IF EXISTS "anon can select events"              ON "public"."events";
DROP POLICY IF EXISTS "anon can select notifications"       ON "public"."notifications";
DROP POLICY IF EXISTS "anon can select preferred_slots"     ON "public"."preferred_slots";
DROP POLICY IF EXISTS "anon can select proposed_time_notes" ON "public"."proposed_time_notes";

-- ------------------------------------------------------------
-- 2. Tighten realtime broadcast policies from anon to authenticated.
--    Logged-in users still receive broadcasts (they carry the
--    `authenticated` role); anonymous visitors no longer can.
-- ------------------------------------------------------------
DROP POLICY IF EXISTS "anon can receive broadcasts" ON "realtime"."messages";
DROP POLICY IF EXISTS "anon can send broadcasts"    ON "realtime"."messages";

CREATE POLICY "authenticated can receive broadcasts"
  ON "realtime"."messages" FOR SELECT TO "authenticated" USING (true);

CREATE POLICY "authenticated can send broadcasts"
  ON "realtime"."messages" FOR INSERT TO "authenticated" WITH CHECK (true);

-- ------------------------------------------------------------
-- 3. Make events.coordinator_id nullable and change the FK to
--    ON DELETE SET NULL. When a user deletes their account,
--    confirmed events they coordinated remain visible to the
--    other participants but the coordinator link is wiped.
--    The frontend renders NULL coordinator as "Deleted user".
-- ------------------------------------------------------------
ALTER TABLE "public"."events"
  ALTER COLUMN "coordinator_id" DROP NOT NULL;

ALTER TABLE "public"."events"
  DROP CONSTRAINT IF EXISTS "events_coordinator_id_fkey";

ALTER TABLE "public"."events"
  ADD CONSTRAINT "events_coordinator_id_fkey"
  FOREIGN KEY ("coordinator_id")
  REFERENCES "public"."profiles"("id")
  ON DELETE SET NULL;

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- SELECT policyname FROM pg_policies WHERE policyname LIKE 'anon%';   -- expect: 0 rows
-- SELECT policyname, roles FROM pg_policies
--   WHERE schemaname='realtime' AND tablename='messages';             -- expect: roles={authenticated}
-- SELECT is_nullable FROM information_schema.columns
--   WHERE table_name='events' AND column_name='coordinator_id';       -- expect: YES
-- SELECT confdeltype FROM pg_constraint
--   WHERE conname='events_coordinator_id_fkey';                       -- expect: 'n' (SET NULL)
