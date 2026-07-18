-- ============================================================
-- Agentic chat: chat_threads / chat_messages (LangGraph assistant)
-- ============================================================
-- Date: 2026-07-18
-- Purpose: Add persistence for the agentic chat feature (see
--          LangGraph_Agentic_Chat_Plan.md §1). The LangGraph graph is
--          stateless across turns — workflow state (status/workflow/draft/
--          participants/pending_person/candidate_slots/booking_mode/
--          last_event_uid) is persisted on chat_threads and rehydrated by
--          the backend's entry router on every POST /api/chat/threads/{id}/turn.
--
--          Two new enums (chat_thread_status_enum, chat_role_enum), two new
--          tables (chat_threads, chat_messages), RLS on both scoped to
--          `user_id = auth.uid()` (chat_messages via its owning thread).
--          Strictly single-user: all chat-table access goes through the
--          AUTHED client (get_authed_client) — no service_client usage for
--          these tables, and they are NOT added to supabase_realtime.
--
-- Apply via Supabase SQL Editor or:
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20260718000001_agentic_chat.sql
--
-- Idempotent: safe to re-run (guarded CREATE TYPE, IF NOT EXISTS tables,
-- DROP POLICY IF EXISTS before CREATE POLICY).
-- ============================================================

BEGIN;

-- Enums (CREATE TYPE has no IF NOT EXISTS in Postgres — guard via DO block).
DO $$ BEGIN
    CREATE TYPE "public"."chat_thread_status_enum" AS ENUM (
        'idle',
        'collecting',
        'awaiting_email',
        'awaiting_choice',
        'awaiting_confirmation'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE "public"."chat_role_enum" AS ENUM (
        'user',
        'assistant'
    );
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Tables

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
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "chat_threads_pkey" PRIMARY KEY ("id")
);

CREATE TABLE IF NOT EXISTS "public"."chat_messages" (
    "id" "uuid" DEFAULT "gen_random_uuid"() NOT NULL,
    "thread_id" "uuid" NOT NULL,
    "role" "public"."chat_role_enum" NOT NULL,
    "content" "text" NOT NULL,
    "payload" "jsonb",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "chat_messages_pkey" PRIMARY KEY ("id")
);

-- Foreign keys (guarded — IF NOT EXISTS isn't valid on ADD CONSTRAINT, so
-- check pg_constraint first for idempotent re-runs).
DO $$ BEGIN
    ALTER TABLE ONLY "public"."chat_threads"
        ADD CONSTRAINT "chat_threads_user_id_fkey"
        FOREIGN KEY ("user_id") REFERENCES "public"."profiles"("id") ON DELETE CASCADE;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    ALTER TABLE ONLY "public"."chat_messages"
        ADD CONSTRAINT "chat_messages_thread_id_fkey"
        FOREIGN KEY ("thread_id") REFERENCES "public"."chat_threads"("id") ON DELETE CASCADE;
EXCEPTION
    WHEN duplicate_object THEN NULL;
END $$;

-- Indexes
CREATE INDEX IF NOT EXISTS "chat_threads_user_id_idx" ON "public"."chat_threads" USING "btree" ("user_id");
CREATE INDEX IF NOT EXISTS "chat_messages_thread_id_created_at_idx" ON "public"."chat_messages" USING "btree" ("thread_id", "created_at");

-- updated_at trigger (public.set_updated_at already exists in schema.sql).
DROP TRIGGER IF EXISTS "chat_threads_updated_at" ON "public"."chat_threads";
CREATE TRIGGER "chat_threads_updated_at" BEFORE UPDATE ON "public"."chat_threads"
    FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();

-- RLS
ALTER TABLE "public"."chat_threads" ENABLE ROW LEVEL SECURITY;
ALTER TABLE "public"."chat_messages" ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "chat_threads_own" ON "public"."chat_threads";
CREATE POLICY "chat_threads_own" ON "public"."chat_threads"
    USING (("user_id" = "auth"."uid"()))
    WITH CHECK (("user_id" = "auth"."uid"()));

DROP POLICY IF EXISTS "chat_messages_own" ON "public"."chat_messages";
CREATE POLICY "chat_messages_own" ON "public"."chat_messages"
    USING ((EXISTS ( SELECT 1
       FROM "public"."chat_threads"
      WHERE (("chat_threads"."id" = "chat_messages"."thread_id") AND ("chat_threads"."user_id" = "auth"."uid"())))))
    WITH CHECK ((EXISTS ( SELECT 1
       FROM "public"."chat_threads"
      WHERE (("chat_threads"."id" = "chat_messages"."thread_id") AND ("chat_threads"."user_id" = "auth"."uid"())))));

-- Grants (table-level; RLS above is the real enforcement layer — same
-- pattern as every other user-owned table in schema.sql).
GRANT ALL ON TABLE "public"."chat_threads" TO "anon";
GRANT ALL ON TABLE "public"."chat_threads" TO "authenticated";
GRANT ALL ON TABLE "public"."chat_threads" TO "service_role";

GRANT ALL ON TABLE "public"."chat_messages" TO "anon";
GRANT ALL ON TABLE "public"."chat_messages" TO "authenticated";
GRANT ALL ON TABLE "public"."chat_messages" TO "service_role";

COMMIT;

-- ============================================================
-- Verification queries (run after migration to confirm)
-- ============================================================
-- -- Both tables exist with RLS enabled (expect 2 rows, rowsecurity = true):
-- SELECT tablename, rowsecurity FROM pg_tables
--   WHERE schemaname = 'public' AND tablename IN ('chat_threads', 'chat_messages');
--
-- -- Both policies exist:
-- SELECT tablename, policyname, cmd FROM pg_policies
--   WHERE schemaname = 'public' AND tablename IN ('chat_threads', 'chat_messages')
--   ORDER BY tablename, policyname;
--
-- -- Enums exist with the expected labels:
-- SELECT t.typname, e.enumlabel FROM pg_type t
--   JOIN pg_enum e ON e.enumtypid = t.oid
--   WHERE t.typname IN ('chat_thread_status_enum', 'chat_role_enum')
--   ORDER BY t.typname, e.enumsortorder;
-- ============================================================
