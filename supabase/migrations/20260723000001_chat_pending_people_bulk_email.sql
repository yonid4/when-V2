-- ============================================================
-- Agentic chat: rename chat_threads.pending_person → pending_people
-- ============================================================
-- Date: 2026-07-23
-- Purpose: The chat agent now asks for every missing participant email in ONE
--          bulk prompt instead of one round-trip per name. The workflow state it
--          rehydrates changes from a single pending person ({name, reason, …})
--          to a LIST of them, so the jsonb column is renamed to the plural and
--          any in-flight value is reshaped from a lone object to a one-element
--          array. Null (the common case — only awaiting_email threads carry a
--          value) stays null.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260723000001_chat_pending_people_bulk_email.sql
--
-- Idempotent: the rename is guarded on the old column still existing; the
-- reshape only touches values that are still a bare object, so a re-run (where
-- the column is already renamed and values are arrays) is a no-op.
-- ============================================================

BEGIN;

-- Rename the column (guarded so a re-run after the rename does nothing).
DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = 'chat_threads'
          AND column_name = 'pending_person'
    ) THEN
        ALTER TABLE "public"."chat_threads"
            RENAME COLUMN "pending_person" TO "pending_people";
    END IF;
END $$;

-- Reshape any in-flight single-person value into a one-element array so mid-turn
-- awaiting_email threads keep resolving. Arrays and nulls are left untouched.
UPDATE "public"."chat_threads"
   SET "pending_people" = "jsonb_build_array"("pending_people")
 WHERE "pending_people" IS NOT NULL
   AND "jsonb_typeof"("pending_people") = 'object';

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Column renamed (expect one row, column_name = 'pending_people'):
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_schema = 'public' AND table_name = 'chat_threads'
--     AND column_name IN ('pending_person', 'pending_people');
--
-- -- No object-shaped values remain (expect 0):
-- SELECT count(*) FROM public.chat_threads
--   WHERE pending_people IS NOT NULL AND jsonb_typeof(pending_people) <> 'array';
-- ============================================================
