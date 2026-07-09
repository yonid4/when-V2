-- ============================================================
-- Allow event_participants self-delete / "leave event" (bug fix M2)
-- ============================================================
-- Date: 2026-07-07
-- Purpose: Repair the silently-broken "leave event" feature. The only DELETE
--          policy on public.event_participants was:
--            CREATE POLICY "event_participants_delete"
--              ON public.event_participants FOR DELETE
--              USING (EXISTS (SELECT 1 FROM events
--                             WHERE events.id = event_participants.event_id
--                               AND events.coordinator_id = auth.uid()));
--          i.e. the coordinator only.
--
--          participant_service.remove_participant already does the correct
--          app-level authorization (allow the delete when is_coordinator OR
--          is_self, else 403) and issues the DELETE through the AUTHED client.
--          But when a NON-coordinator participant tries to leave (self-removal),
--          the authed DELETE matches ZERO rows at the RLS layer — the coordinator
--          policy's USING clause is false for them — so result.data is empty and
--          the service raises 404. The "leave event" feature is silently broken.
--
--          Fix: add a narrowly-scoped DELETE policy that lets a participant
--          delete only their OWN row (user_id = auth.uid()). This keeps RLS as
--          the enforcement layer (a core invariant) and needs NO Python change —
--          remove_participant already has the right app-level check and uses the
--          authed client; it was only being blocked by the missing policy.
--          Coordinator removals continue to flow through the existing
--          event_participants_delete policy; the two policies are permissive and
--          OR together.
--
--          No GRANT is required: the authenticated role already holds table-level
--          DELETE on public.event_participants (the existing coordinator DELETE
--          policy works, which proves the privilege is present).
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260707000001_allow_participant_self_delete.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

-- Allow a participant to delete (leave) only their own row.
DROP POLICY IF EXISTS "event_participants_delete_self" ON "public"."event_participants";
CREATE POLICY "event_participants_delete_self" ON "public"."event_participants"
    FOR DELETE
    USING (("user_id" = "auth"."uid"()));

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Both DELETE policies now exist (expect 2 rows: event_participants_delete
-- -- and event_participants_delete_self):
-- SELECT policyname, cmd, qual FROM pg_policies
--   WHERE schemaname = 'public' AND tablename = 'event_participants'
--     AND cmd = 'DELETE'
--   ORDER BY policyname;
-- -- Self-delete policy is scoped to the caller's own row (expect 1 row; qual
-- -- "(user_id = auth.uid())"):
-- SELECT policyname, cmd, qual FROM pg_policies
--   WHERE schemaname = 'public' AND tablename = 'event_participants'
--     AND policyname = 'event_participants_delete_self';
