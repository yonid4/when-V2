


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



-- ============================================================
-- EXTENSIONS
-- ============================================================
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






-- ============================================================
-- ENUMS
-- ============================================================
CREATE TYPE "public"."event_status_enum" AS ENUM (
    'planning',
    'confirmed',
    'cancelled'
);


ALTER TYPE "public"."event_status_enum" OWNER TO "postgres";


CREATE TYPE "public"."event_type_enum" AS ENUM (
    'meeting',
    'social',
    'birthday',
    'other'
);


ALTER TYPE "public"."event_type_enum" OWNER TO "postgres";


CREATE TYPE "public"."invitation_status_enum" AS ENUM (
    'pending',
    'accepted',
    'declined'
);


ALTER TYPE "public"."invitation_status_enum" OWNER TO "postgres";


CREATE TYPE "public"."notification_type_enum" AS ENUM (
    'event_invitation',
    'event_finalized',
    'event_deleted',
    'event_time_changed',
    'invite_accepted'
);


ALTER TYPE "public"."notification_type_enum" OWNER TO "postgres";


CREATE TYPE "public"."participant_status_enum" AS ENUM (
    'invited',
    'accepted',
    'declined',
    'maybe'
);


ALTER TYPE "public"."participant_status_enum" OWNER TO "postgres";


CREATE TYPE "public"."rsvp_status_enum" AS ENUM (
    'going',
    'maybe',
    'not_going',
    'pending'
);


ALTER TYPE "public"."rsvp_status_enum" OWNER TO "postgres";


-- ============================================================
-- FUNCTIONS
-- ============================================================

-- Broadcast trigger functions
CREATE OR REPLACE FUNCTION "public"."broadcast_event_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.id, OLD.id)::text,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    NEW,
    OLD
  );
  RETURN NULL;
END;
$$;


ALTER FUNCTION "public"."broadcast_event_changes"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."broadcast_notification_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'user:' || COALESCE(NEW.user_id, OLD.user_id)::text,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    NEW,
    OLD
  );
  RETURN NULL;
END;
$$;


ALTER FUNCTION "public"."broadcast_notification_changes"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."broadcast_participant_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    NEW,
    OLD
  );
  RETURN NULL;
END;
$$;


ALTER FUNCTION "public"."broadcast_participant_changes"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."broadcast_preferred_slots_changes"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    NEW,
    OLD
  );
  RETURN NULL;
END;
$$;


ALTER FUNCTION "public"."broadcast_preferred_slots_changes"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."busy_slots_broadcast_trigger"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'user:' || COALESCE(NEW.user_id, OLD.user_id)::text || ':busy_slots';

  PERFORM realtime.broadcast_changes(
    _topic,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    COALESCE(NEW, OLD),
    OLD
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."busy_slots_broadcast_trigger"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."clear_write_calendar_for_user"("p_user_id" "uuid", "p_exclude_source_id" "uuid") RETURNS "void"
    LANGUAGE "sql" SECURITY DEFINER
    AS $$
    UPDATE calendar_sources cs
    SET is_write_calendar = false
    FROM calendar_accounts ca
    WHERE cs.account_id = ca.id
      AND ca.user_id = p_user_id
      AND cs.id != p_exclude_source_id;
$$;


ALTER FUNCTION "public"."clear_write_calendar_for_user"("p_user_id" "uuid", "p_exclude_source_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."enforce_single_write_calendar"() RETURNS "trigger"
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


CREATE OR REPLACE FUNCTION "public"."event_participants_broadcast_trigger"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':participants';

  PERFORM realtime.broadcast_changes(
    _topic,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    COALESCE(NEW, OLD),
    OLD
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."event_participants_broadcast_trigger"() OWNER TO "postgres";


-- Auto-creates a profile row when a new auth.users row is inserted
CREATE OR REPLACE FUNCTION "public"."handle_new_user"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
begin
  insert into profiles (id, full_name, avatar_url, email_address)
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


ALTER FUNCTION "public"."handle_new_user"() OWNER TO "postgres";


-- Cross-schema trigger: fires handle_new_user on every new auth signup
-- (pg_dump cannot capture auth-schema triggers; added manually)
CREATE TRIGGER "on_auth_user_created"
  AFTER INSERT ON "auth"."users"
  FOR EACH ROW EXECUTE FUNCTION "public"."handle_new_user"();


CREATE OR REPLACE FUNCTION "public"."handle_preferred_slots_broadcast"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':preferred_slots',
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    NEW,
    OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."handle_preferred_slots_broadcast"() OWNER TO "postgres";


-- Helper: check participation without triggering RLS (avoids mutual recursion)
CREATE OR REPLACE FUNCTION "public"."is_event_participant"("p_event_id" "uuid", "p_user_id" "uuid") RETURNS boolean
    LANGUAGE "sql" STABLE SECURITY DEFINER
    AS $$
  select exists (
    select 1 from event_participants
    where event_id = p_event_id
      and user_id = p_user_id
  );
$$;


ALTER FUNCTION "public"."is_event_participant"("p_event_id" "uuid", "p_user_id" "uuid") OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."notifications_broadcast_trigger"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'user:' || COALESCE(NEW.user_id, OLD.user_id)::text || ':notifications';

  PERFORM realtime.broadcast_changes(
    _topic,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    COALESCE(NEW, OLD),
    OLD
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."notifications_broadcast_trigger"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."preferred_slots_broadcast_trigger"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':preferred_slots';

  PERFORM realtime.broadcast_changes(
    _topic,
    TG_OP,
    TG_OP,
    TG_TABLE_NAME,
    TG_TABLE_SCHEMA,
    COALESCE(NEW, OLD),
    OLD
  );

  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."preferred_slots_broadcast_trigger"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."proposed_time_notes_broadcast_trigger"() RETURNS "trigger"
    LANGUAGE "plpgsql" SECURITY DEFINER
    AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_uid, OLD.event_uid)::text || ':proposed_time_notes',
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, COALESCE(NEW, OLD), OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;


ALTER FUNCTION "public"."proposed_time_notes_broadcast_trigger"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
begin
  new.updated_at = now();
  return new;
end;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";

-- ============================================================
-- TABLES
-- ============================================================

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."busy_slots" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "calendar_source_id" "uuid" NOT NULL,
    "provider_event_id" character varying(255) NOT NULL,
    "start_time_utc" timestamp with time zone NOT NULL,
    "end_time_utc" timestamp with time zone NOT NULL,
    "last_synced_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."busy_slots" REPLICA IDENTITY FULL;


ALTER TABLE "public"."busy_slots" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."calendar_accounts" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "provider" character varying(50) DEFAULT 'google'::character varying NOT NULL,
    "provider_email" character varying(255) NOT NULL,
    "provider_account_id" character varying(255) NOT NULL,
    "credentials" "jsonb" NOT NULL,
    "connected_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "last_synced_at" timestamp with time zone,
    "needs_reauth" boolean DEFAULT false NOT NULL,
    CONSTRAINT "calendar_accounts_provider_check" CHECK ((("provider")::"text" = ANY (ARRAY['google'::"text", 'microsoft'::"text"])))
);


ALTER TABLE "public"."calendar_accounts" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."calendar_sources" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "account_id" "uuid" NOT NULL,
    "calendar_id" character varying(255) NOT NULL,
    "calendar_name" character varying(255) NOT NULL,
    "is_enabled" boolean DEFAULT true NOT NULL,
    "is_write_calendar" boolean DEFAULT false NOT NULL,
    "color" character varying(20),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "is_writable" boolean DEFAULT true NOT NULL,
    CONSTRAINT "calendar_sources_write_requires_writable" CHECK (("is_writable" OR NOT "is_write_calendar"))
);


ALTER TABLE "public"."calendar_sources" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_invitations" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "event_id" "uuid" NOT NULL,
    "inviter_id" "uuid" NOT NULL,
    "invitee_id" "uuid",
    "invitee_email" character varying(255) NOT NULL,
    "status" "public"."invitation_status_enum" DEFAULT 'pending'::"public"."invitation_status_enum" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."event_invitations" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."event_participants" (
    "event_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "status" "public"."participant_status_enum" DEFAULT 'invited'::"public"."participant_status_enum" NOT NULL,
    "rsvp_status" "public"."rsvp_status_enum",
    "can_invite" boolean DEFAULT false NOT NULL,
    "joined_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."event_participants" REPLICA IDENTITY FULL;


ALTER TABLE "public"."event_participants" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."events" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "uid" character varying(12) NOT NULL,
    "name" "text" NOT NULL,
    "description" "text",
    "event_type" "public"."event_type_enum" DEFAULT 'meeting'::"public"."event_type_enum" NOT NULL,
    "coordinator_id" "uuid",
    "earliest_datetime_utc" timestamp with time zone NOT NULL,
    "latest_datetime_utc" timestamp with time zone NOT NULL,
    "duration_minutes" integer NOT NULL,
    "status" "public"."event_status_enum" DEFAULT 'planning'::"public"."event_status_enum" NOT NULL,
    "location" "text",
    "video_call_link" "text",
    "finalized_start_time_utc" timestamp with time zone,
    "finalized_end_time_utc" timestamp with time zone,
    "calendar_event_id" "text",
    "proposals_needs_regeneration" boolean DEFAULT true NOT NULL,
    "proposals_last_generated_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "finalized_at" timestamp with time zone,
    "allow_guest_invites" boolean DEFAULT false NOT NULL,
    CONSTRAINT "events_duration_minutes_check" CHECK (("duration_minutes" > 0)),
    CONSTRAINT "events_window_valid" CHECK (("latest_datetime_utc" > "earliest_datetime_utc"))
);

ALTER TABLE ONLY "public"."events" REPLICA IDENTITY FULL;


ALTER TABLE "public"."events" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."notifications" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "event_id" "uuid",
    "notification_type" "public"."notification_type_enum" NOT NULL,
    "title" "text" NOT NULL,
    "message" "text" NOT NULL,
    "is_read" boolean DEFAULT false NOT NULL,
    "action_taken" boolean DEFAULT false NOT NULL,
    "action_type" character varying(50),
    "metadata" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "read_at" timestamp with time zone,
    "action_at" timestamp with time zone
);

ALTER TABLE ONLY "public"."notifications" REPLICA IDENTITY FULL;


ALTER TABLE "public"."notifications" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."preferred_slots" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "event_id" "uuid" NOT NULL,
    "start_time_utc" timestamp with time zone NOT NULL,
    "end_time_utc" timestamp with time zone NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);

ALTER TABLE ONLY "public"."preferred_slots" REPLICA IDENTITY FULL;


ALTER TABLE "public"."preferred_slots" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."profiles" (
    "id" "uuid" NOT NULL,
    "full_name" character varying(255),
    "avatar_url" "text",
    "email_address" character varying(255) NOT NULL,
    "timezone" character varying(50) DEFAULT 'UTC'::character varying,
    "primary_calendar_provider" "text" DEFAULT 'google'::"text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."profiles" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."proposed_time_notes" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "proposed_time_id" "uuid" NOT NULL,
    "user_id" "uuid" NOT NULL,
    "content" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "event_uid" "text" NOT NULL
);

ALTER TABLE ONLY "public"."proposed_time_notes" REPLICA IDENTITY FULL;


ALTER TABLE "public"."proposed_time_notes" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."proposed_times" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "event_id" "uuid" NOT NULL,
    "start_time_utc" timestamp with time zone NOT NULL,
    "end_time_utc" timestamp with time zone NOT NULL,
    "conflicts" integer DEFAULT 0 NOT NULL,
    "reasoning" "text",
    "rank" integer NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "preferred_count" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."proposed_times" OWNER TO "postgres";


-- ============================================================
-- PRIMARY KEYS & UNIQUE CONSTRAINTS
-- ============================================================

ALTER TABLE ONLY "public"."busy_slots"
    ADD CONSTRAINT "busy_slots_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."busy_slots"
    ADD CONSTRAINT "busy_slots_provider_event_id_calendar_source_id_key" UNIQUE ("provider_event_id", "calendar_source_id");



ALTER TABLE ONLY "public"."calendar_accounts"
    ADD CONSTRAINT "calendar_accounts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."calendar_accounts"
    ADD CONSTRAINT "calendar_accounts_user_id_provider_provider_account_id_key" UNIQUE ("user_id", "provider", "provider_account_id");



ALTER TABLE ONLY "public"."calendar_sources"
    ADD CONSTRAINT "calendar_sources_account_id_calendar_id_key" UNIQUE ("account_id", "calendar_id");



ALTER TABLE ONLY "public"."calendar_sources"
    ADD CONSTRAINT "calendar_sources_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."event_invitations"
    ADD CONSTRAINT "event_invitations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."event_participants"
    ADD CONSTRAINT "event_participants_pkey" PRIMARY KEY ("event_id", "user_id");



ALTER TABLE ONLY "public"."events"
    ADD CONSTRAINT "events_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."events"
    ADD CONSTRAINT "events_uid_key" UNIQUE ("uid");



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."preferred_slots"
    ADD CONSTRAINT "preferred_slots_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."preferred_slots"
    ADD CONSTRAINT "preferred_slots_user_id_event_id_start_time_utc_end_time_ut_key" UNIQUE ("user_id", "event_id", "start_time_utc", "end_time_utc");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_email_address_key" UNIQUE ("email_address");



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."proposed_time_notes"
    ADD CONSTRAINT "proposed_time_notes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."proposed_times"
    ADD CONSTRAINT "proposed_times_event_id_rank_key" UNIQUE ("event_id", "rank");



ALTER TABLE ONLY "public"."proposed_times"
    ADD CONSTRAINT "proposed_times_pkey" PRIMARY KEY ("id");



-- ============================================================
-- INDEXES
-- ============================================================

CREATE INDEX "busy_slots_time_range_idx" ON "public"."busy_slots" USING "btree" ("user_id", "start_time_utc", "end_time_utc");



CREATE INDEX "busy_slots_user_id_idx" ON "public"."busy_slots" USING "btree" ("user_id");



CREATE INDEX "calendar_accounts_user_id_idx" ON "public"."calendar_accounts" USING "btree" ("user_id");



CREATE INDEX "calendar_sources_account_id_idx" ON "public"."calendar_sources" USING "btree" ("account_id");



CREATE INDEX "event_invitations_event_id_idx" ON "public"."event_invitations" USING "btree" ("event_id");



CREATE INDEX "event_invitations_invitee_email_idx" ON "public"."event_invitations" USING "btree" ("invitee_email");



CREATE INDEX "event_invitations_invitee_id_idx" ON "public"."event_invitations" USING "btree" ("invitee_id");



CREATE INDEX "event_participants_user_id_idx" ON "public"."event_participants" USING "btree" ("user_id");



CREATE INDEX "events_coordinator_id_idx" ON "public"."events" USING "btree" ("coordinator_id");



CREATE INDEX "events_uid_idx" ON "public"."events" USING "btree" ("uid");



CREATE INDEX "notifications_user_id_idx" ON "public"."notifications" USING "btree" ("user_id");



CREATE INDEX "notifications_user_unread_idx" ON "public"."notifications" USING "btree" ("user_id", "is_read") WHERE ("is_read" = false);



CREATE UNIQUE INDEX IF NOT EXISTS "notifications_unique_pending_invitation" ON "public"."notifications" ("user_id", "event_id") WHERE ("notification_type" = 'event_invitation' AND "action_taken" = false);



CREATE INDEX "preferred_slots_event_id_idx" ON "public"."preferred_slots" USING "btree" ("event_id");



CREATE INDEX "preferred_slots_user_id_idx" ON "public"."preferred_slots" USING "btree" ("user_id");



CREATE INDEX "proposed_time_notes_event_uid_idx" ON "public"."proposed_time_notes" USING "btree" ("event_uid");



CREATE INDEX "proposed_time_notes_proposed_time_id_idx" ON "public"."proposed_time_notes" USING "btree" ("proposed_time_id");



CREATE INDEX "proposed_time_notes_user_id_idx" ON "public"."proposed_time_notes" USING "btree" ("user_id");



CREATE INDEX "proposed_times_event_id_idx" ON "public"."proposed_times" USING "btree" ("event_id");



-- ============================================================
-- TRIGGERS
-- ============================================================

CREATE OR REPLACE TRIGGER "broadcast_events" AFTER INSERT OR DELETE OR UPDATE ON "public"."events" FOR EACH ROW EXECUTE FUNCTION "public"."broadcast_event_changes"();



CREATE OR REPLACE TRIGGER "broadcast_notifications" AFTER INSERT OR DELETE OR UPDATE ON "public"."notifications" FOR EACH ROW EXECUTE FUNCTION "public"."broadcast_notification_changes"();



CREATE OR REPLACE TRIGGER "broadcast_participants" AFTER INSERT OR DELETE OR UPDATE ON "public"."event_participants" FOR EACH ROW EXECUTE FUNCTION "public"."broadcast_participant_changes"();



CREATE OR REPLACE TRIGGER "broadcast_preferred_slots" AFTER INSERT OR DELETE OR UPDATE ON "public"."preferred_slots" FOR EACH ROW EXECUTE FUNCTION "public"."broadcast_preferred_slots_changes"();



CREATE OR REPLACE TRIGGER "busy_slots_broadcast" AFTER INSERT OR DELETE OR UPDATE ON "public"."busy_slots" FOR EACH ROW EXECUTE FUNCTION "public"."busy_slots_broadcast_trigger"();



CREATE OR REPLACE TRIGGER "busy_slots_updated_at" BEFORE UPDATE ON "public"."busy_slots" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "calendar_sources_single_write" BEFORE INSERT OR UPDATE OF "is_write_calendar" ON "public"."calendar_sources" FOR EACH ROW WHEN (NEW.is_write_calendar) EXECUTE FUNCTION "public"."enforce_single_write_calendar"();



CREATE OR REPLACE TRIGGER "calendar_sources_updated_at" BEFORE UPDATE ON "public"."calendar_sources" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "event_invitations_updated_at" BEFORE UPDATE ON "public"."event_invitations" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "event_participants_broadcast" AFTER INSERT OR DELETE OR UPDATE ON "public"."event_participants" FOR EACH ROW EXECUTE FUNCTION "public"."event_participants_broadcast_trigger"();



CREATE OR REPLACE TRIGGER "events_updated_at" BEFORE UPDATE ON "public"."events" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "notifications_broadcast" AFTER INSERT OR DELETE OR UPDATE ON "public"."notifications" FOR EACH ROW EXECUTE FUNCTION "public"."notifications_broadcast_trigger"();



CREATE OR REPLACE TRIGGER "preferred_slots_broadcast" AFTER INSERT OR DELETE OR UPDATE ON "public"."preferred_slots" FOR EACH ROW EXECUTE FUNCTION "public"."handle_preferred_slots_broadcast"();



CREATE OR REPLACE TRIGGER "profiles_updated_at" BEFORE UPDATE ON "public"."profiles" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "proposed_time_notes_broadcast" AFTER INSERT OR DELETE OR UPDATE ON "public"."proposed_time_notes" FOR EACH ROW EXECUTE FUNCTION "public"."proposed_time_notes_broadcast_trigger"();



-- ============================================================
-- FOREIGN KEYS
-- ============================================================

ALTER TABLE ONLY "public"."busy_slots"
    ADD CONSTRAINT "busy_slots_calendar_source_id_fkey" FOREIGN KEY ("calendar_source_id") REFERENCES "public"."calendar_sources"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."busy_slots"
    ADD CONSTRAINT "busy_slots_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."calendar_accounts"
    ADD CONSTRAINT "calendar_accounts_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."calendar_sources"
    ADD CONSTRAINT "calendar_sources_account_id_fkey" FOREIGN KEY ("account_id") REFERENCES "public"."calendar_accounts"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."event_invitations"
    ADD CONSTRAINT "event_invitations_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."event_invitations"
    ADD CONSTRAINT "event_invitations_invitee_id_fkey" FOREIGN KEY ("invitee_id") REFERENCES "public"."profiles"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."event_invitations"
    ADD CONSTRAINT "event_invitations_inviter_id_fkey" FOREIGN KEY ("inviter_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."event_participants"
    ADD CONSTRAINT "event_participants_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."event_participants"
    ADD CONSTRAINT "event_participants_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."events"
    ADD CONSTRAINT "events_coordinator_id_fkey" FOREIGN KEY ("coordinator_id") REFERENCES "public"."profiles"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."notifications"
    ADD CONSTRAINT "notifications_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."preferred_slots"
    ADD CONSTRAINT "preferred_slots_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."preferred_slots"
    ADD CONSTRAINT "preferred_slots_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."profiles"
    ADD CONSTRAINT "profiles_id_fkey" FOREIGN KEY ("id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."proposed_time_notes"
    ADD CONSTRAINT "proposed_time_notes_proposed_time_id_fkey" FOREIGN KEY ("proposed_time_id") REFERENCES "public"."proposed_times"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."proposed_time_notes"
    ADD CONSTRAINT "proposed_time_notes_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "auth"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."proposed_times"
    ADD CONSTRAINT "proposed_times_event_id_fkey" FOREIGN KEY ("event_id") REFERENCES "public"."events"("id") ON DELETE CASCADE;



-- ============================================================
-- RLS — enable on all tables
-- ============================================================

-- ============================================================
-- RLS POLICIES
-- ============================================================

ALTER TABLE "public"."busy_slots" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "busy_slots_select_own" ON "public"."busy_slots" FOR SELECT USING (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."calendar_accounts" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "calendar_accounts_own" ON "public"."calendar_accounts" USING (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."calendar_sources" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "calendar_sources_own" ON "public"."calendar_sources" USING ((EXISTS ( SELECT 1
   FROM "public"."calendar_accounts"
  WHERE (("calendar_accounts"."id" = "calendar_sources"."account_id") AND ("calendar_accounts"."user_id" = "auth"."uid"())))));



ALTER TABLE "public"."event_invitations" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "event_invitations_insert" ON "public"."event_invitations" FOR INSERT WITH CHECK (((EXISTS ( SELECT 1
   FROM "public"."events"
  WHERE (("events"."id" = "event_invitations"."event_id") AND ("events"."coordinator_id" = "auth"."uid"())))) OR (EXISTS ( SELECT 1
   FROM "public"."event_participants"
  WHERE (("event_participants"."event_id" = "event_invitations"."event_id") AND ("event_participants"."user_id" = "auth"."uid"()) AND ("event_participants"."can_invite" = true))))));



CREATE POLICY "event_invitations_select" ON "public"."event_invitations" FOR SELECT USING ((("inviter_id" = "auth"."uid"()) OR ("invitee_id" = "auth"."uid"())));



CREATE POLICY "event_invitations_update" ON "public"."event_invitations" FOR UPDATE USING ((("inviter_id" = "auth"."uid"()) OR ("invitee_id" = "auth"."uid"())));



ALTER TABLE "public"."event_participants" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "event_participants_delete" ON "public"."event_participants" FOR DELETE USING ((EXISTS ( SELECT 1
   FROM "public"."events"
  WHERE (("events"."id" = "event_participants"."event_id") AND ("events"."coordinator_id" = "auth"."uid"())))));



CREATE POLICY "event_participants_delete_self" ON "public"."event_participants" FOR DELETE USING (("user_id" = "auth"."uid"()));



CREATE POLICY "event_participants_insert" ON "public"."event_participants" FOR INSERT WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."events"
  WHERE (("events"."id" = "event_participants"."event_id") AND ("events"."coordinator_id" = "auth"."uid"())))));



CREATE POLICY "event_participants_select" ON "public"."event_participants" FOR SELECT USING ((("user_id" = "auth"."uid"()) OR "public"."is_event_participant"("event_id", "auth"."uid"())));



CREATE POLICY "event_participants_update_self" ON "public"."event_participants" FOR UPDATE USING (("user_id" = "auth"."uid"())) WITH CHECK (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."events" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "events_delete" ON "public"."events" FOR DELETE USING (("coordinator_id" = "auth"."uid"()));



CREATE POLICY "events_insert" ON "public"."events" FOR INSERT WITH CHECK (("coordinator_id" = "auth"."uid"()));



CREATE POLICY "events_select" ON "public"."events" FOR SELECT USING ((("coordinator_id" = "auth"."uid"()) OR "public"."is_event_participant"("id", "auth"."uid"())));



CREATE POLICY "events_update" ON "public"."events" FOR UPDATE USING (("coordinator_id" = "auth"."uid"()));



ALTER TABLE "public"."notifications" ENABLE ROW LEVEL SECURITY;


-- Legacy duplicate of notifications_select_own (same predicate). Kept to match
-- the live database; functionally redundant and safe to drop.
CREATE POLICY "Users can only read own notifications" ON "public"."notifications" FOR SELECT USING (("auth"."uid"() = "user_id"));


CREATE POLICY "notifications_select_own" ON "public"."notifications" FOR SELECT USING (("auth"."uid"() = "user_id"));



CREATE POLICY "notifications_update_own" ON "public"."notifications" FOR UPDATE USING (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."preferred_slots" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "preferred_slots_select" ON "public"."preferred_slots" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."event_participants"
  WHERE (("event_participants"."event_id" = "preferred_slots"."event_id") AND ("event_participants"."user_id" = "auth"."uid"())))));



CREATE POLICY "preferred_slots_write_own" ON "public"."preferred_slots" USING (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."profiles" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "profiles_select_own" ON "public"."profiles" FOR SELECT USING (("auth"."uid"() = "id"));



CREATE POLICY "profiles_update_own" ON "public"."profiles" FOR UPDATE USING (("auth"."uid"() = "id"));



ALTER TABLE "public"."proposed_time_notes" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "proposed_time_notes_delete" ON "public"."proposed_time_notes" FOR DELETE USING (("user_id" = "auth"."uid"()));



CREATE POLICY "proposed_time_notes_insert" ON "public"."proposed_time_notes" FOR INSERT WITH CHECK (("user_id" = "auth"."uid"()));



CREATE POLICY "proposed_time_notes_realtime_select" ON "public"."proposed_time_notes" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM ("public"."event_participants" "ep"
     JOIN "public"."events" "e" ON (("e"."id" = "ep"."event_id")))
  WHERE ((("e"."uid")::"text" = "proposed_time_notes"."event_uid") AND ("ep"."user_id" = "auth"."uid"())))));



CREATE POLICY "proposed_time_notes_select" ON "public"."proposed_time_notes" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM ("public"."proposed_times" "pt"
     JOIN "public"."event_participants" "ep" ON (("ep"."event_id" = "pt"."event_id")))
  WHERE (("pt"."id" = "proposed_time_notes"."proposed_time_id") AND ("ep"."user_id" = "auth"."uid"())))));



ALTER TABLE "public"."proposed_times" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "proposed_times_select" ON "public"."proposed_times" FOR SELECT USING ((EXISTS ( SELECT 1
   FROM "public"."event_participants"
  WHERE (("event_participants"."event_id" = "proposed_times"."event_id") AND ("event_participants"."user_id" = "auth"."uid"())))));





-- ============================================================
-- REALTIME — replica identity, publication, cross-schema policies
-- ============================================================

ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";






ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."busy_slots";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."event_participants";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."events";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."notifications";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."preferred_slots";



ALTER PUBLICATION "supabase_realtime" ADD TABLE ONLY "public"."proposed_time_notes";



-- RLS policies for realtime.messages (pg_dump cannot capture cross-schema objects)
-- Broadcasts are readable only via topic-scoped SELECT policies; there is no
-- INSERT policy, so clients cannot send broadcasts
-- (see supabase/migrations/20260706000001_scope_realtime_broadcast_policies.sql).
CREATE POLICY "event coordinator can read participants topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING ((("topic" ~~ 'event:%:participants'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."events" "e"
  WHERE (("e"."coordinator_id" = "auth"."uid"()) AND ("e"."id" = ("split_part"("messages"."topic", ':'::"text", 2))::"uuid"))))));

CREATE POLICY "event coordinator can read preferred slots topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING ((("topic" ~~ 'event:%:preferred_slots'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."events" "e"
  WHERE (("e"."coordinator_id" = "auth"."uid"()) AND ("e"."id" = ("split_part"("messages"."topic", ':'::"text", 2))::"uuid"))))));

CREATE POLICY "event participants can read participants topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING ((("topic" ~~ 'event:%:participants'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."event_participants" "ep"
  WHERE (("ep"."user_id" = "auth"."uid"()) AND ("ep"."event_id" = ("split_part"("messages"."topic", ':'::"text", 2))::"uuid"))))));

CREATE POLICY "event participants can read preferred slots topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING ((("topic" ~~ 'event:%:preferred_slots'::"text") AND (EXISTS ( SELECT 1
   FROM "public"."event_participants" "ep"
  WHERE (("ep"."user_id" = "auth"."uid"()) AND ("ep"."event_id" = ("split_part"("messages"."topic", ':'::"text", 2))::"uuid"))))));

ALTER TABLE "realtime"."messages" ENABLE ROW LEVEL SECURITY;

CREATE POLICY "user can read busy_slots topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING (("topic" = (('user:'::"text" || ("auth"."uid"())::"text") || ':busy_slots'::"text")));

CREATE POLICY "user can read notifications topic" ON "realtime"."messages" FOR SELECT TO "authenticated" USING (("topic" = (('user:'::"text" || ("auth"."uid"())::"text") || ':notifications'::"text")));



-- ============================================================
-- GRANTS
-- ============================================================

GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";






















































































































































GRANT ALL ON FUNCTION "public"."broadcast_event_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."broadcast_event_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."broadcast_event_changes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."broadcast_notification_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."broadcast_notification_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."broadcast_notification_changes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."broadcast_participant_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."broadcast_participant_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."broadcast_participant_changes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."broadcast_preferred_slots_changes"() TO "anon";
GRANT ALL ON FUNCTION "public"."broadcast_preferred_slots_changes"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."broadcast_preferred_slots_changes"() TO "service_role";



GRANT ALL ON FUNCTION "public"."busy_slots_broadcast_trigger"() TO "anon";
GRANT ALL ON FUNCTION "public"."busy_slots_broadcast_trigger"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."busy_slots_broadcast_trigger"() TO "service_role";



-- SECURITY DEFINER with no internal auth check: executable by service_role only
-- (see supabase/migrations/20260706000003_revoke_clear_write_calendar_grants.sql).
REVOKE ALL ON FUNCTION "public"."clear_write_calendar_for_user"("p_user_id" "uuid", "p_exclude_source_id" "uuid") FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."clear_write_calendar_for_user"("p_user_id" "uuid", "p_exclude_source_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."enforce_single_write_calendar"() TO "anon";
GRANT ALL ON FUNCTION "public"."enforce_single_write_calendar"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."enforce_single_write_calendar"() TO "service_role";



GRANT ALL ON FUNCTION "public"."event_participants_broadcast_trigger"() TO "anon";
GRANT ALL ON FUNCTION "public"."event_participants_broadcast_trigger"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."event_participants_broadcast_trigger"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_new_user"() TO "service_role";



GRANT ALL ON FUNCTION "public"."handle_preferred_slots_broadcast"() TO "anon";
GRANT ALL ON FUNCTION "public"."handle_preferred_slots_broadcast"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."handle_preferred_slots_broadcast"() TO "service_role";



GRANT ALL ON FUNCTION "public"."is_event_participant"("p_event_id" "uuid", "p_user_id" "uuid") TO "anon";
GRANT ALL ON FUNCTION "public"."is_event_participant"("p_event_id" "uuid", "p_user_id" "uuid") TO "authenticated";
GRANT ALL ON FUNCTION "public"."is_event_participant"("p_event_id" "uuid", "p_user_id" "uuid") TO "service_role";



GRANT ALL ON FUNCTION "public"."notifications_broadcast_trigger"() TO "anon";
GRANT ALL ON FUNCTION "public"."notifications_broadcast_trigger"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."notifications_broadcast_trigger"() TO "service_role";



GRANT ALL ON FUNCTION "public"."preferred_slots_broadcast_trigger"() TO "anon";
GRANT ALL ON FUNCTION "public"."preferred_slots_broadcast_trigger"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."preferred_slots_broadcast_trigger"() TO "service_role";



GRANT ALL ON FUNCTION "public"."proposed_time_notes_broadcast_trigger"() TO "anon";
GRANT ALL ON FUNCTION "public"."proposed_time_notes_broadcast_trigger"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."proposed_time_notes_broadcast_trigger"() TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";


















GRANT ALL ON TABLE "public"."busy_slots" TO "anon";
GRANT ALL ON TABLE "public"."busy_slots" TO "authenticated";
GRANT ALL ON TABLE "public"."busy_slots" TO "service_role";



GRANT ALL ON TABLE "public"."calendar_accounts" TO "anon";
GRANT ALL ON TABLE "public"."calendar_accounts" TO "authenticated";
GRANT ALL ON TABLE "public"."calendar_accounts" TO "service_role";



GRANT ALL ON TABLE "public"."calendar_sources" TO "anon";
GRANT ALL ON TABLE "public"."calendar_sources" TO "authenticated";
GRANT ALL ON TABLE "public"."calendar_sources" TO "service_role";



GRANT ALL ON TABLE "public"."event_invitations" TO "anon";
GRANT ALL ON TABLE "public"."event_invitations" TO "authenticated";
GRANT ALL ON TABLE "public"."event_invitations" TO "service_role";



-- authenticated may UPDATE only rsvp_status; anon holds no UPDATE at all
-- (see supabase/migrations/20260706000002_restrict_event_participants_self_update.sql).
GRANT INSERT,SELECT,DELETE,TRUNCATE,REFERENCES,TRIGGER ON TABLE "public"."event_participants" TO "anon";
GRANT INSERT,SELECT,DELETE,TRUNCATE,REFERENCES,TRIGGER ON TABLE "public"."event_participants" TO "authenticated";
GRANT UPDATE("rsvp_status") ON TABLE "public"."event_participants" TO "authenticated";
GRANT ALL ON TABLE "public"."event_participants" TO "service_role";



GRANT ALL ON TABLE "public"."events" TO "anon";
GRANT ALL ON TABLE "public"."events" TO "authenticated";
GRANT ALL ON TABLE "public"."events" TO "service_role";



GRANT ALL ON TABLE "public"."notifications" TO "anon";
GRANT ALL ON TABLE "public"."notifications" TO "authenticated";
GRANT ALL ON TABLE "public"."notifications" TO "service_role";



GRANT ALL ON TABLE "public"."preferred_slots" TO "anon";
GRANT ALL ON TABLE "public"."preferred_slots" TO "authenticated";
GRANT ALL ON TABLE "public"."preferred_slots" TO "service_role";



GRANT ALL ON TABLE "public"."profiles" TO "anon";
GRANT ALL ON TABLE "public"."profiles" TO "authenticated";
GRANT ALL ON TABLE "public"."profiles" TO "service_role";



GRANT ALL ON TABLE "public"."proposed_time_notes" TO "anon";
GRANT ALL ON TABLE "public"."proposed_time_notes" TO "authenticated";
GRANT ALL ON TABLE "public"."proposed_time_notes" TO "service_role";



GRANT ALL ON TABLE "public"."proposed_times" TO "anon";
GRANT ALL ON TABLE "public"."proposed_times" TO "authenticated";
GRANT ALL ON TABLE "public"."proposed_times" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";



-- ============================================================
-- AGENTIC CHAT (single-user assistant)
--
-- Per-user chat threads + messages backing the LangGraph assistant. The graph
-- itself is stateless: workflow state is persisted on the chat_threads row
-- between turns (status/workflow/draft/participants/pending_person/
-- candidate_slots/booking_mode/last_event_uid). Strictly single-user — all
-- access is via the authenticated user's client (get_authed_client), guarded by
-- the RLS policies below. These tables are NOT added to supabase_realtime.
-- ============================================================

CREATE TYPE "public"."chat_thread_status_enum" AS ENUM (
    'idle',
    'collecting',
    'awaiting_email',
    'awaiting_choice',
    'awaiting_confirmation'
);


ALTER TYPE "public"."chat_thread_status_enum" OWNER TO "postgres";


CREATE TYPE "public"."chat_role_enum" AS ENUM (
    'user',
    'assistant'
);


ALTER TYPE "public"."chat_role_enum" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."chat_threads" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "user_id" "uuid" NOT NULL,
    "title" "text",
    "status" "public"."chat_thread_status_enum" DEFAULT 'idle'::"public"."chat_thread_status_enum" NOT NULL,
    "workflow" "text",
    "draft" "jsonb",
    "participants" "jsonb",
    "pending_person" "jsonb",
    "candidate_slots" "jsonb",
    "booking_mode" "text",
    "last_event_uid" character varying(12),
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."chat_threads" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."chat_messages" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "thread_id" "uuid" NOT NULL,
    "role" "public"."chat_role_enum" NOT NULL,
    "content" "text" NOT NULL,
    "payload" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."chat_messages" OWNER TO "postgres";


ALTER TABLE ONLY "public"."chat_threads"
    ADD CONSTRAINT "chat_threads_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id");



CREATE INDEX "chat_threads_user_id_idx" ON "public"."chat_threads" USING "btree" ("user_id");



CREATE INDEX "chat_messages_thread_id_created_at_idx" ON "public"."chat_messages" USING "btree" ("thread_id", "created_at");



CREATE OR REPLACE TRIGGER "chat_threads_updated_at" BEFORE UPDATE ON "public"."chat_threads" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



ALTER TABLE ONLY "public"."chat_threads"
    ADD CONSTRAINT "chat_threads_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."chat_messages"
    ADD CONSTRAINT "chat_messages_thread_id_fkey" FOREIGN KEY ("thread_id") REFERENCES "public"."chat_threads"("id") ON DELETE CASCADE;



ALTER TABLE "public"."chat_threads" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "chat_threads_own" ON "public"."chat_threads" USING (("user_id" = "auth"."uid"())) WITH CHECK (("user_id" = "auth"."uid"()));



ALTER TABLE "public"."chat_messages" ENABLE ROW LEVEL SECURITY;


CREATE POLICY "chat_messages_own" ON "public"."chat_messages" USING ((EXISTS ( SELECT 1
   FROM "public"."chat_threads"
  WHERE (("chat_threads"."id" = "chat_messages"."thread_id") AND ("chat_threads"."user_id" = "auth"."uid"()))))) WITH CHECK ((EXISTS ( SELECT 1
   FROM "public"."chat_threads"
  WHERE (("chat_threads"."id" = "chat_messages"."thread_id") AND ("chat_threads"."user_id" = "auth"."uid"())))));



GRANT ALL ON TABLE "public"."chat_threads" TO "anon";
GRANT ALL ON TABLE "public"."chat_threads" TO "authenticated";
GRANT ALL ON TABLE "public"."chat_threads" TO "service_role";



GRANT ALL ON TABLE "public"."chat_messages" TO "anon";
GRANT ALL ON TABLE "public"."chat_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."chat_messages" TO "service_role";































