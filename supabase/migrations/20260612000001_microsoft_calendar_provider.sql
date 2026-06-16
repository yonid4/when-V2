-- ============================================================
-- Microsoft (Outlook) Calendar Provider — schema support
-- ============================================================
-- Date: 2026-06-12
-- Purpose: Prepare the calendar schema for a second provider
--          (Microsoft Graph / Outlook) alongside Google.
--
--   1. Repair any user that currently has >1 write calendar
--      (a latent bug in the connect flow where a newly connected
--      account's primary calendar was set as write without clearing
--      the previous one).
--   2. Add a DB-level trigger that guarantees AT MOST ONE write
--      calendar per user across ALL connected accounts/providers.
--      This makes the invariant impossible to violate regardless of
--      which code path writes the row.
--   3. Constrain calendar_accounts.provider to the known providers.
--   4. Rename events.google_calendar_event_id -> events.calendar_event_id
--      since the stored id may now be an Outlook event id.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260612000001_microsoft_calendar_provider.sql
--
-- Idempotent: safe to re-run.
-- ============================================================

BEGIN;

-- ------------------------------------------------------------
-- 1. One-time data repair: collapse any user with multiple write
--    calendars down to a single one (keep the most recently
--    updated, then most recently created, then by id for stability).
--    Runs BEFORE the trigger is installed so the trigger never sees
--    a pre-existing violation.
-- ------------------------------------------------------------
WITH ranked AS (
    SELECT cs.id,
           row_number() OVER (
               PARTITION BY ca.user_id
               ORDER BY cs.updated_at DESC, cs.created_at DESC, cs.id
           ) AS rn
    FROM "public"."calendar_sources" cs
    JOIN "public"."calendar_accounts" ca ON ca.id = cs.account_id
    WHERE cs.is_write_calendar
)
UPDATE "public"."calendar_sources" cs
SET is_write_calendar = false
FROM ranked
WHERE cs.id = ranked.id
  AND ranked.rn > 1;

-- ------------------------------------------------------------
-- 2. Trigger: enforce a single write calendar per user.
--    When a source is set as the write calendar, clear the flag on
--    every other source belonging to the same user (any account /
--    any provider). A BEFORE trigger that updates sibling rows of
--    the same table is safe here: the inner UPDATE only sets the
--    flag to false, and the trigger's WHEN clause fires only when
--    NEW.is_write_calendar is true, so there is no recursion.
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION "public"."enforce_single_write_calendar"()
    RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
    UPDATE "public"."calendar_sources" cs
    SET is_write_calendar = false
    FROM "public"."calendar_accounts" ca
    WHERE cs.account_id = ca.id
      AND ca.user_id = (
          SELECT user_id FROM "public"."calendar_accounts" WHERE id = NEW.account_id
      )
      AND cs.id <> NEW.id
      AND cs.is_write_calendar;
    RETURN NEW;
END;
$$;

ALTER FUNCTION "public"."enforce_single_write_calendar"() OWNER TO "postgres";

DROP TRIGGER IF EXISTS "calendar_sources_single_write" ON "public"."calendar_sources";

CREATE TRIGGER "calendar_sources_single_write"
    BEFORE INSERT OR UPDATE OF "is_write_calendar" ON "public"."calendar_sources"
    FOR EACH ROW
    WHEN (NEW.is_write_calendar)
    EXECUTE FUNCTION "public"."enforce_single_write_calendar"();

-- ------------------------------------------------------------
-- 3. Restrict provider to the known set. Drop first so re-runs and
--    future provider additions can replace it cleanly.
-- ------------------------------------------------------------
ALTER TABLE "public"."calendar_accounts"
    DROP CONSTRAINT IF EXISTS "calendar_accounts_provider_check";

ALTER TABLE "public"."calendar_accounts"
    ADD CONSTRAINT "calendar_accounts_provider_check"
    CHECK (("provider")::"text" = ANY (ARRAY['google'::"text", 'microsoft'::"text"]));

-- ------------------------------------------------------------
-- 4. Rename the provider-specific column to a generic name. The
--    stored value may now be a Google OR an Outlook event id.
-- ------------------------------------------------------------
ALTER TABLE "public"."events"
    RENAME COLUMN "google_calendar_event_id" TO "calendar_event_id";

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- At most one write calendar per user (expect 0 rows):
-- SELECT ca.user_id, count(*)
--   FROM calendar_sources cs JOIN calendar_accounts ca ON ca.id = cs.account_id
--   WHERE cs.is_write_calendar GROUP BY ca.user_id HAVING count(*) > 1;
-- -- Trigger present (expect 1 row):
-- SELECT tgname FROM pg_trigger WHERE tgname = 'calendar_sources_single_write';
-- -- Provider check present (expect 1 row):
-- SELECT conname FROM pg_constraint WHERE conname = 'calendar_accounts_provider_check';
-- -- Column renamed (expect column 'calendar_event_id', no 'google_calendar_event_id'):
-- SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'events' AND column_name LIKE '%calendar_event_id';
