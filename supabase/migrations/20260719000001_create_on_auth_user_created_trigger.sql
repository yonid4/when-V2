-- Create the on_auth_user_created trigger that schema.sql has always documented
-- but which was never actually created in the hosted database (confirmed absent
-- via pg_trigger on 2026-07-19). Without it, any signup that crashes between
-- auth.admin.create_user() succeeding and the backend's profile upsert leaves an
-- orphaned auth.users row with no profiles row — and that account can never log
-- in again: create_user fails with "already registered" and the profiles-lookup
-- fallback in auth_service._upsert_profile finds nothing, returning 500.
--
-- Hardened relative to the previously documented function body: the trigger
-- fires inside GoTrue's session, whose search_path does not include "public",
-- so the table reference must be schema-qualified and search_path pinned —
-- otherwise every INSERT into auth.users (i.e. every signup) would error.

CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    SET "search_path" = ''
    AS $$
begin
  insert into public.profiles (id, full_name, avatar_url, email_address)
  values (
    new.id,
    new.raw_user_meta_data->>'full_name',
    new.raw_user_meta_data->>'avatar_url',
    new.email
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

DROP TRIGGER IF EXISTS "on_auth_user_created" ON "auth"."users";
CREATE TRIGGER "on_auth_user_created"
  AFTER INSERT ON "auth"."users"
  FOR EACH ROW EXECUTE FUNCTION "public"."handle_new_user"();

-- Backfill: repair every auth.users row the missing trigger orphaned (28 rows
-- as of 2026-07-19: shalom.halon@gmail.com plus itest-* integration-test
-- accounts). Targetless ON CONFLICT also skips the pathological case where an
-- orphan's raw email collides with another profile's email_address.
INSERT INTO "public"."profiles" ("id", "full_name", "avatar_url", "email_address")
SELECT u."id",
       u."raw_user_meta_data"->>'full_name',
       u."raw_user_meta_data"->>'avatar_url',
       u."email"
FROM "auth"."users" u
LEFT JOIN "public"."profiles" p ON p."id" = u."id"
WHERE p."id" IS NULL
ON CONFLICT DO NOTHING;
