-- ============================================================
-- Revoke client EXECUTE on clear_write_calendar_for_user (security fix M3)
-- ============================================================
-- Date: 2026-07-06
-- Purpose: Close a cross-user tampering hole. The function
--            public.clear_write_calendar_for_user(p_user_id uuid,
--                                                 p_exclude_source_id uuid)
--          is SECURITY DEFINER (owner postgres, bypasses RLS), takes an
--          arbitrary p_user_id, performs no internal auth check, and was
--          granted to anon/authenticated/service_role (GRANT ALL). Any user —
--          even anonymous — could call it via PostgREST RPC
--          (POST /rest/v1/rpc/clear_write_calendar_for_user) to clear another
--          user's write-calendar flags.
--
--          It is dead code in the product: no backend/app or frontend code
--          calls it (the only callers are backend integration tests, which use
--          the service client and are unaffected). The one-write-calendar
--          invariant is actually enforced by the calendar_sources_single_write
--          BEFORE trigger (enforce_single_write_calendar).
--
--          Fix: revoke EXECUTE from PUBLIC, anon, and authenticated;
--          service_role keeps EXECUTE. We deliberately do NOT drop the
--          function (conservative fix; the trigger owns the invariant, and the
--          integration tests still exercise the RPC via service_role).
--
--          FROM PUBLIC is included defensively: Postgres grants EXECUTE to
--          PUBLIC by default on new functions and every role inherits PUBLIC.
--          The live schema dump contains NO "REVOKE ... FROM PUBLIC" for this
--          function (or any object) — only the three GRANT ALL lines to
--          anon/authenticated/service_role — so the implicit PUBLIC EXECUTE
--          was never revoked and revoking only anon/authenticated would leave
--          the RPC reachable through PUBLIC.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260706000003_revoke_clear_write_calendar_grants.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

REVOKE ALL ON FUNCTION "public"."clear_write_calendar_for_user"("uuid", "uuid") FROM PUBLIC;
REVOKE ALL ON FUNCTION "public"."clear_write_calendar_for_user"("uuid", "uuid") FROM "anon";
REVOKE ALL ON FUNCTION "public"."clear_write_calendar_for_user"("uuid", "uuid") FROM "authenticated";

-- service_role keeps EXECUTE (explicit re-grant for a self-documenting end state).
GRANT ALL ON FUNCTION "public"."clear_write_calendar_for_user"("uuid", "uuid") TO "service_role";

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Only service_role (plus owner postgres) may execute (expect no anon/
-- -- authenticated/PUBLIC rows):
-- SELECT grantee, privilege_type FROM information_schema.routine_privileges
--   WHERE routine_schema = 'public'
--     AND routine_name = 'clear_write_calendar_for_user';
-- -- Raw ACL view (expect postgres=X/postgres and service_role=X/postgres only;
-- -- a NULL proacl would mean default PUBLIC execute — must NOT be NULL):
-- SELECT proacl FROM pg_proc
--   WHERE oid = 'public.clear_write_calendar_for_user(uuid, uuid)'::regprocedure;
