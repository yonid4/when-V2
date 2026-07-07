-- ============================================================
-- Restrict event_participants self-update (security fix H3)
-- ============================================================
-- Date: 2026-07-06
-- Purpose: Close a privilege-escalation hole. The only UPDATE policy on
--          public.event_participants was:
--            CREATE POLICY "event_participants_update_self"
--              ON public.event_participants FOR UPDATE
--              USING (user_id = auth.uid());
--          No WITH CHECK and no column restriction, so a participant hitting
--          Supabase directly with the anon key + their own JWT could:
--            - set can_invite = true on their own row (self-escalation; the
--              event_invitations insert policy then lets them invite arbitrary
--              emails, bypassing the coordinator-only control), and
--            - re-point event_id/user_id on their row (no WITH CHECK re-check
--              of the updated row, subject only to other constraints).
--
--          Fix, two layers:
--            1. Recreate the policy with WITH CHECK (user_id = auth.uid())
--               so an update cannot move the row to another user/identity.
--            2. Column-level privilege: the authenticated role may UPDATE only
--               rsvp_status — the sole column participants legitimately
--               self-update (backend update_rsvp). can_invite / status /
--               event_id / user_id / joined_at become non-updatable for
--               authenticated regardless of RLS. service_role keeps full
--               UPDATE for backend-privileged writes.
--          Hygiene: anon also held UPDATE via a legacy GRANT ALL; it passes no
--          policy (auth.uid() is NULL) so this was inert, but revoke it anyway.
--
-- Note (aggravating discovery, live-verified): coordinator permission grants
-- were ALREADY broken at the DB layer — participant_service.update_permissions
-- ran through the authed client, and the self-only USING filter matched zero
-- rows when the coordinator targeted another user's row (0 rows updated →
-- backend 404). This migration pairs with the backend change that switches
-- update_permissions' write to the service client (after its app-side
-- coordinator check), which actually repairs that feature.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260706000002_restrict_event_participants_self_update.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

-- 1. Recreate the self-update policy with WITH CHECK (blocks row re-pointing).
DROP POLICY IF EXISTS "event_participants_update_self" ON "public"."event_participants";
CREATE POLICY "event_participants_update_self" ON "public"."event_participants"
    FOR UPDATE
    USING (("user_id" = "auth"."uid"()))
    WITH CHECK (("user_id" = "auth"."uid"()));

-- 2. Column-level UPDATE privilege: authenticated may only set rsvp_status.
REVOKE UPDATE ON TABLE "public"."event_participants" FROM "authenticated";
GRANT UPDATE ("rsvp_status") ON TABLE "public"."event_participants" TO "authenticated";

-- 3. Hygiene: anon never passes the policy, but should not hold UPDATE at all.
REVOKE UPDATE ON TABLE "public"."event_participants" FROM "anon";

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Policy recreated with WITH CHECK (expect 1 row; qual and with_check both
-- -- "(user_id = auth.uid())"):
-- SELECT policyname, cmd, qual, with_check FROM pg_policies
--   WHERE schemaname = 'public' AND tablename = 'event_participants'
--     AND policyname = 'event_participants_update_self';
-- -- Column-level UPDATE for authenticated is rsvp_status only (expect 1 row):
-- SELECT grantee, column_name, privilege_type
--   FROM information_schema.column_privileges
--   WHERE table_schema = 'public' AND table_name = 'event_participants'
--     AND privilege_type = 'UPDATE' AND grantee IN ('anon', 'authenticated');
-- -- No table-wide UPDATE for anon/authenticated (expect 0 rows):
-- SELECT grantee FROM information_schema.table_privileges
--   WHERE table_schema = 'public' AND table_name = 'event_participants'
--     AND privilege_type = 'UPDATE' AND grantee IN ('anon', 'authenticated');
