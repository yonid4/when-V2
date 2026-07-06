-- ============================================================
-- Scope realtime.messages broadcast policies (security fix H2)
-- ============================================================
-- Date: 2026-07-06
-- Purpose: Close a cross-user data exposure. Four broad RLS policies on
--          realtime.messages granted every authenticated user unrestricted
--          broadcast access:
--            - SELECT USING (true)  x2 (duplicate pair)
--            - INSERT WITH CHECK (true) x2 (duplicate pair)
--          Because the frontend ships the public anon key, any logged-in user
--          could open a private channel on any topic (user:<uuid>:notifications,
--          event:<id>, ...:busy_slots, ...:preferred_slots) and receive full-row
--          payloads — the broadcast-source tables are REPLICA IDENTITY FULL, so
--          broadcasts carry complete rows, bypassing per-table SELECT RLS.
--          The broad INSERT pair additionally let any authenticated user forge
--          broadcast messages into topics other users can read.
--
--          This migration drops all four broad policies. The six topic-scoped
--          SELECT policies already in place remain untouched and become the only
--          read path — they ARE the topic-ownership scoping the fix calls for:
--            - event coordinator / participants can read event:%:participants
--            - event coordinator / participants can read event:%:preferred_slots
--            - user can read user:<own uid>:busy_slots
--            - user can read user:<own uid>:notifications
--          No INSERT policy remains: clients cannot send broadcasts at all.
--
-- Caveat (verified against the live realtime schema): realtime.send and
-- realtime.broadcast_changes are NOT SECURITY DEFINER, so trigger-driven
-- broadcast sends run as the DML role. With the broad INSERT policies gone,
-- sends from non-BYPASSRLS roles (e.g. `authenticated` via the RLS-respecting
-- backend client) are silently suppressed by realtime.send's WHEN OTHERS
-- RAISE WARNING handler. This is acceptable: nothing consumes broadcasts —
-- the frontend subscribes only via postgres_changes and presence (which this
-- table's policies do not affect), and the backend has no realtime consumer.
--
-- Follow-up cleanup (out of scope here): the five plain-invoker (non-SECURITY
-- DEFINER) broadcast trigger functions — broadcast_event_changes,
-- broadcast_notification_changes, broadcast_participant_changes,
-- broadcast_preferred_slots_changes, handle_preferred_slots_broadcast — are
-- legacy dead weight; their topics (event:<id>, user:<uuid>,
-- event:<id>:preferred_slots) have no consumer, and their sends may now be
-- suppressed for authenticated-role DML. They should be dropped or converted
-- deliberately in a later change, not silently here.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260706000001_scope_realtime_broadcast_policies.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

DROP POLICY IF EXISTS "authenticated can receive broadcasts" ON "realtime"."messages";
DROP POLICY IF EXISTS "authenticated can send broadcasts" ON "realtime"."messages";
DROP POLICY IF EXISTS "authenticated users can receive broadcasts" ON "realtime"."messages";
DROP POLICY IF EXISTS "authenticated users can send broadcasts" ON "realtime"."messages";

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Broad policies gone (expect 0 rows):
-- SELECT policyname FROM pg_policies
--   WHERE schemaname = 'realtime' AND tablename = 'messages'
--     AND policyname IN (
--       'authenticated can receive broadcasts',
--       'authenticated can send broadcasts',
--       'authenticated users can receive broadcasts',
--       'authenticated users can send broadcasts');
-- -- Six scoped SELECT policies remain (expect 6 rows, all cmd = SELECT):
-- SELECT policyname, cmd FROM pg_policies
--   WHERE schemaname = 'realtime' AND tablename = 'messages';
-- -- RLS still enabled (expect relrowsecurity = true):
-- SELECT relrowsecurity FROM pg_class
--   WHERE oid = 'realtime.messages'::regclass;
