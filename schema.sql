-- When. v2 — Database Schema
-- Run this in Supabase SQL Editor (or psql against your Supabase project)
-- Assumes auth.users table already exists (provided by Supabase Auth)

-- ============================================================
-- EXTENSIONS
-- ============================================================
create extension if not exists "pgcrypto";


-- ============================================================
-- ENUMS
-- ============================================================
create type event_type_enum as enum ('meeting', 'social', 'birthday', 'other');
create type event_status_enum as enum ('planning', 'confirmed', 'cancelled');
create type participant_status_enum as enum ('invited', 'accepted', 'declined', 'maybe');
create type rsvp_status_enum as enum ('pending', 'going', 'maybe', 'not_going');
create type invitation_status_enum as enum ('pending', 'accepted', 'declined');
create type notification_type_enum as enum (
  'event_invitation',
  'invite_accepted',
  'event_finalized',
  'event_deleted',
  'event_time_changed'
);


-- ============================================================
-- profiles
-- ============================================================
create table profiles (
  id                        uuid primary key references auth.users(id) on delete cascade,
  full_name                 varchar(255),
  avatar_url                text,
  email_address             varchar(255) unique not null,
  timezone                  varchar(50) default 'UTC',
  primary_calendar_provider text default 'google',
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

-- Auto-update updated_at
create or replace function set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create trigger profiles_updated_at
  before update on profiles
  for each row execute function set_updated_at();


-- ============================================================
-- events
-- ============================================================
create table events (
  id                          uuid primary key default gen_random_uuid(),
  uid                         varchar(12) unique not null,
  name                        text not null,
  description                 text,
  event_type                  event_type_enum not null default 'meeting',
  coordinator_id              uuid not null references profiles(id) on delete restrict,
  earliest_datetime_utc       timestamptz not null,
  latest_datetime_utc         timestamptz not null,
  duration_minutes            int not null check (duration_minutes > 0),
  status                      event_status_enum not null default 'planning',
  location                    text,
  video_call_link             text,
  allow_guest_invites         boolean not null default false,
  finalized_start_time_utc    timestamptz,
  finalized_end_time_utc      timestamptz,
  google_calendar_event_id    text,
  proposals_needs_regeneration boolean not null default true,
  proposals_last_generated_at timestamptz,
  created_at                  timestamptz not null default now(),
  updated_at                  timestamptz not null default now(),
  finalized_at                timestamptz,
  constraint events_window_valid check (latest_datetime_utc > earliest_datetime_utc)
);

create index events_coordinator_id_idx on events(coordinator_id);
create index events_uid_idx on events(uid);

create trigger events_updated_at
  before update on events
  for each row execute function set_updated_at();


-- ============================================================
-- event_participants
-- ============================================================
create table event_participants (
  event_id   uuid not null references events(id) on delete cascade,
  user_id    uuid not null references profiles(id) on delete cascade,
  status     participant_status_enum not null default 'invited',
  rsvp_status rsvp_status_enum,
  can_invite boolean not null default false,
  joined_at  timestamptz not null default now(),
  primary key (event_id, user_id)
);

create index event_participants_user_id_idx on event_participants(user_id);


-- ============================================================
-- event_invitations
-- ============================================================
create table event_invitations (
  id             uuid primary key default gen_random_uuid(),
  event_id       uuid not null references events(id) on delete cascade,
  inviter_id     uuid not null references profiles(id) on delete cascade,
  invitee_id     uuid references profiles(id) on delete set null,
  invitee_email  varchar(255) not null,
  status         invitation_status_enum not null default 'pending',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

create index event_invitations_event_id_idx on event_invitations(event_id);
create index event_invitations_invitee_email_idx on event_invitations(invitee_email);
create index event_invitations_invitee_id_idx on event_invitations(invitee_id);

create trigger event_invitations_updated_at
  before update on event_invitations
  for each row execute function set_updated_at();


-- ============================================================
-- calendar_accounts
-- ============================================================
create table calendar_accounts (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references profiles(id) on delete cascade,
  provider            varchar(50) not null default 'google',
  provider_email      varchar(255) not null,
  provider_account_id varchar(255) not null,
  credentials         jsonb not null,
  connected_at        timestamptz not null default now(),
  last_synced_at      timestamptz,
  unique (user_id, provider, provider_account_id)
);

create index calendar_accounts_user_id_idx on calendar_accounts(user_id);


-- ============================================================
-- calendar_sources
-- ============================================================
create table calendar_sources (
  id                uuid primary key default gen_random_uuid(),
  account_id        uuid not null references calendar_accounts(id) on delete cascade,
  calendar_id       varchar(255) not null,
  calendar_name     varchar(255) not null,
  is_enabled        boolean not null default true,
  is_write_calendar boolean not null default false,
  color             varchar(20),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now()
);

create index calendar_sources_account_id_idx on calendar_sources(account_id);
alter table calendar_sources add constraint calendar_sources_account_id_calendar_id_key unique (account_id, calendar_id);

create trigger calendar_sources_updated_at
  before update on calendar_sources
  for each row execute function set_updated_at();


-- ============================================================
-- busy_slots
-- NOTE: user_id references auth.users(id), not profiles(id)
-- They share the same UUID — see DATA_MODEL.md for details
-- ============================================================
create table busy_slots (
  id                  uuid primary key default gen_random_uuid(),
  user_id             uuid not null references auth.users(id) on delete cascade,
  calendar_source_id  uuid not null references calendar_sources(id) on delete cascade,
  provider_event_id   varchar(255) not null,
  start_time_utc      timestamptz not null,
  end_time_utc        timestamptz not null,
  last_synced_at      timestamptz not null default now(),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now(),
  unique (provider_event_id, calendar_source_id)
);

create index busy_slots_user_id_idx on busy_slots(user_id);
create index busy_slots_time_range_idx on busy_slots(user_id, start_time_utc, end_time_utc);

create trigger busy_slots_updated_at
  before update on busy_slots
  for each row execute function set_updated_at();


-- ============================================================
-- preferred_slots
-- ============================================================
create table preferred_slots (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null references profiles(id) on delete cascade,
  event_id       uuid not null references events(id) on delete cascade,
  start_time_utc timestamptz not null,
  end_time_utc   timestamptz not null,
  created_at     timestamptz not null default now(),
  unique (user_id, event_id, start_time_utc, end_time_utc)
);

create index preferred_slots_event_id_idx on preferred_slots(event_id);
create index preferred_slots_user_id_idx on preferred_slots(user_id);


-- ============================================================
-- proposed_times
-- ============================================================
create table proposed_times (
  id              uuid primary key default gen_random_uuid(),
  event_id        uuid not null references events(id) on delete cascade,
  start_time_utc  timestamptz not null,
  end_time_utc    timestamptz not null,
  conflicts       int not null default 0,
  preferred_count int not null default 0,
  reasoning       text,
  rank            int not null,
  created_at      timestamptz not null default now(),
  unique (event_id, rank)
);

create index proposed_times_event_id_idx on proposed_times(event_id);


-- ============================================================
-- proposed_time_notes
-- ============================================================
create table proposed_time_notes (
  id                uuid        primary key default gen_random_uuid(),
  proposed_time_id  uuid        not null references proposed_times(id) on delete cascade,
  user_id           uuid        not null references auth.users(id) on delete cascade,
  content           text        not null,
  event_uid         text        not null,
  created_at        timestamptz not null default now()
);

create index proposed_time_notes_proposed_time_id_idx on proposed_time_notes(proposed_time_id);
create index proposed_time_notes_user_id_idx          on proposed_time_notes(user_id);
create index proposed_time_notes_event_uid_idx        on proposed_time_notes(event_uid);


-- ============================================================
-- notifications
-- ============================================================
create table notifications (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid not null references profiles(id) on delete cascade,
  event_id          uuid references events(id) on delete cascade,
  notification_type notification_type_enum not null,
  title             text not null,
  message           text not null,
  is_read           boolean not null default false,
  action_taken      boolean not null default false,
  action_type       varchar(50),
  metadata          jsonb,
  created_at        timestamptz not null default now(),
  read_at           timestamptz,
  action_at         timestamptz
);

create index notifications_user_id_idx on notifications(user_id);
create index notifications_user_unread_idx on notifications(user_id, is_read) where is_read = false;


-- ============================================================
-- RLS — enable on all tables
-- ============================================================
alter table profiles            enable row level security;
alter table events              enable row level security;
alter table event_participants  enable row level security;
alter table event_invitations   enable row level security;
alter table calendar_accounts   enable row level security;
alter table calendar_sources    enable row level security;
alter table busy_slots          enable row level security;
alter table preferred_slots     enable row level security;
alter table proposed_times          enable row level security;
alter table proposed_time_notes     enable row level security;
alter table notifications           enable row level security;


-- ============================================================
-- RLS POLICIES
-- ============================================================

-- profiles: own row only
create policy "profiles_select_own" on profiles for select using (auth.uid() = id);
create policy "profiles_update_own" on profiles for update using (auth.uid() = id);

-- Helper: check participation without triggering RLS (breaks mutual recursion)
create or replace function is_event_participant(p_event_id uuid, p_user_id uuid)
returns boolean
language sql
security definer
stable
as $$
  select exists (
    select 1 from event_participants
    where event_id = p_event_id
      and user_id = p_user_id
  );
$$;

-- events: coordinator or participant can read; only coordinator can write
create policy "events_select" on events for select using (
  coordinator_id = auth.uid()
  or is_event_participant(id, auth.uid())
);
create policy "events_insert" on events for insert with check (coordinator_id = auth.uid());
create policy "events_update" on events for update using (coordinator_id = auth.uid());
create policy "events_delete" on events for delete using (coordinator_id = auth.uid());

-- event_participants: the participant themselves or any co-participant can read
create policy "event_participants_select" on event_participants for select using (
  user_id = auth.uid()
  or is_event_participant(event_id, auth.uid())
);
-- coordinator can add/remove; self can update RSVP
create policy "event_participants_insert" on event_participants for insert with check (
  exists (select 1 from events where events.id = event_id and events.coordinator_id = auth.uid())
);
create policy "event_participants_update_self" on event_participants for update using (user_id = auth.uid());
create policy "event_participants_delete" on event_participants for delete using (
  exists (select 1 from events where events.id = event_id and events.coordinator_id = auth.uid())
);

-- event_invitations: inviter or invitee can read
create policy "event_invitations_select" on event_invitations for select using (
  inviter_id = auth.uid() or invitee_id = auth.uid()
);
-- coordinator or can_invite participant can insert
create policy "event_invitations_insert" on event_invitations for insert with check (
  exists (select 1 from events where events.id = event_id and events.coordinator_id = auth.uid())
  or exists (
    select 1 from event_participants
    where event_participants.event_id = event_invitations.event_id
      and event_participants.user_id = auth.uid()
      and event_participants.can_invite = true
  )
);
create policy "event_invitations_update" on event_invitations for update using (
  inviter_id = auth.uid() or invitee_id = auth.uid()
);

-- calendar_accounts: own rows only
create policy "calendar_accounts_own" on calendar_accounts for all using (user_id = auth.uid());

-- calendar_sources: own rows (via account)
create policy "calendar_sources_own" on calendar_sources for all using (
  exists (
    select 1 from calendar_accounts
    where calendar_accounts.id = calendar_sources.account_id
      and calendar_accounts.user_id = auth.uid()
  )
);

-- busy_slots: own rows only (read); service role writes
create policy "busy_slots_select_own" on busy_slots for select using (user_id = auth.uid());

-- preferred_slots: all event participants can read; own rows only for write
create policy "preferred_slots_select" on preferred_slots for select using (
  exists (
    select 1 from event_participants
    where event_participants.event_id = preferred_slots.event_id
      and event_participants.user_id = auth.uid()
  )
);
create policy "preferred_slots_write_own" on preferred_slots for all using (user_id = auth.uid());

-- proposed_times: all event participants can read; service role writes
create policy "proposed_times_select" on proposed_times for select using (
  exists (
    select 1 from event_participants
    where event_participants.event_id = proposed_times.event_id
      and event_participants.user_id = auth.uid()
  )
);

-- proposed_time_notes: participants can read; own notes only for write/delete
create policy "proposed_time_notes_select"
  on proposed_time_notes for select
  using (
    exists (
      select 1
      from proposed_times pt
      join event_participants ep on ep.event_id = pt.event_id
      where pt.id = proposed_time_notes.proposed_time_id
        and ep.user_id = auth.uid()
    )
  );

create policy "proposed_time_notes_insert"
  on proposed_time_notes for insert
  with check (user_id = auth.uid());

create policy "proposed_time_notes_delete"
  on proposed_time_notes for delete
  using (user_id = auth.uid());

-- Realtime worker select policy — uses denormalized event_uid to avoid cross-table join
create policy "proposed_time_notes_realtime_select"
  on proposed_time_notes for select
  using (
    exists (
      select 1
      from event_participants ep
      join events e on e.id = ep.event_id
      where e.uid = proposed_time_notes.event_uid
        and ep.user_id = auth.uid()
    )
  );

-- notifications: own rows only (read); service role writes
create policy "notifications_select_own" on notifications for select using (user_id = auth.uid());
create policy "notifications_update_own" on notifications for update using (user_id = auth.uid());


-- ============================================================
-- FUNCTION: clear_write_calendar_for_user
-- Called by update_calendar_source() to enforce is_write_calendar exclusivity.
-- Clears is_write_calendar on all sources owned by p_user_id except p_exclude_source_id.
-- ============================================================
create or replace function public.clear_write_calendar_for_user(
    p_user_id uuid,
    p_exclude_source_id uuid
)
returns void
language sql
security definer
as $$
    update calendar_sources cs
    set is_write_calendar = false
    from calendar_accounts ca
    where cs.account_id = ca.id
      and ca.user_id = p_user_id
      and cs.id != p_exclude_source_id;
$$;


-- ============================================================
-- FUNCTION: handle_new_user
-- Auto-creates a profile row when a new auth.users row is inserted
-- Register as: Auth > Hooks > "After sign-up" in Supabase dashboard,
-- or as a trigger on auth.users if using service role migrations.
-- ============================================================
create or replace function handle_new_user()
returns trigger language plpgsql security definer as $$
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

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function handle_new_user();



-- Replica identity for realtime
ALTER TABLE preferred_slots REPLICA IDENTITY FULL;
ALTER TABLE event_participants REPLICA IDENTITY FULL;
ALTER TABLE busy_slots REPLICA IDENTITY FULL;
ALTER TABLE notifications REPLICA IDENTITY FULL;
ALTER TABLE events REPLICA IDENTITY FULL;
ALTER TABLE proposed_time_notes REPLICA IDENTITY FULL;

-- Realtime publication
ALTER PUBLICATION supabase_realtime ADD TABLE
  preferred_slots, event_participants, busy_slots, notifications, events, proposed_time_notes;

-- Anon RLS policies for realtime
CREATE POLICY "anon can select preferred_slots"
ON public.preferred_slots FOR SELECT TO anon USING (true);

CREATE POLICY "anon can select event_participants"
ON public.event_participants FOR SELECT TO anon USING (true);

CREATE POLICY "anon can select events"
ON public.events FOR SELECT TO anon USING (true);

CREATE POLICY "anon can select notifications"
ON public.notifications FOR SELECT TO anon USING (true);

CREATE POLICY "anon can select busy_slots"
ON public.busy_slots FOR SELECT TO anon USING (true);

-- RLS policies for realtime.messages
CREATE POLICY "anon can receive broadcasts"
ON realtime.messages FOR SELECT TO anon USING (true);

CREATE POLICY "anon can send broadcasts"
ON realtime.messages FOR INSERT TO anon WITH CHECK (true);

CREATE POLICY "anon can select proposed_time_notes"
ON public.proposed_time_notes FOR SELECT TO anon USING (true);


-- ============================================================
-- NOTIFICATIONS RLS FIX
-- Run this block in the Supabase SQL editor if the integration
-- test test_user_cannot_read_another_users_notification fails
-- (Alice can read Bob's notification). This re-creates the
-- select policy and ensures it is correctly scoped.
-- ============================================================
alter table notifications enable row level security;

drop policy if exists "notifications_select_own" on notifications;
create policy "notifications_select_own"
  on notifications for select
  using (auth.uid() = user_id);

-- Also drop and recreate the anon realtime policy with explicit TO anon
-- to ensure it does not inadvertently allow authenticated users to read
-- other users' notifications.
drop policy if exists "anon can select notifications" on public.notifications;
create policy "anon can select notifications"
  on public.notifications for select to anon
  using (true);


-- ============================================================
-- BROADCAST TRIGGER FUNCTIONS
-- These were created via the Supabase dashboard and are captured
-- here for completeness. They power realtime broadcast channels.
-- ============================================================

CREATE OR REPLACE FUNCTION public.broadcast_event_changes() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.id, OLD.id)::text,
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, NEW, OLD
  );
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.broadcast_notification_changes() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'user:' || COALESCE(NEW.user_id, OLD.user_id)::text,
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, NEW, OLD
  );
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.broadcast_participant_changes() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text,
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, NEW, OLD
  );
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.broadcast_preferred_slots_changes() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text,
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, NEW, OLD
  );
  RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.busy_slots_broadcast_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'user:' || COALESCE(NEW.user_id, OLD.user_id)::text || ':busy_slots';
  PERFORM realtime.broadcast_changes(
    _topic, TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, COALESCE(NEW, OLD), OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION public.event_participants_broadcast_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':participants';
  PERFORM realtime.broadcast_changes(
    _topic, TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, COALESCE(NEW, OLD), OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION public.notifications_broadcast_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'user:' || COALESCE(NEW.user_id, OLD.user_id)::text || ':notifications';
  PERFORM realtime.broadcast_changes(
    _topic, TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, COALESCE(NEW, OLD), OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION public.preferred_slots_broadcast_trigger() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  _topic text;
BEGIN
  _topic := 'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':preferred_slots';
  PERFORM realtime.broadcast_changes(
    _topic, TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, COALESCE(NEW, OLD), OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;

CREATE OR REPLACE FUNCTION public.handle_preferred_slots_broadcast() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  PERFORM realtime.broadcast_changes(
    'event:' || COALESCE(NEW.event_id, OLD.event_id)::text || ':preferred_slots',
    TG_OP, TG_OP, TG_TABLE_NAME, TG_TABLE_SCHEMA, NEW, OLD
  );
  RETURN COALESCE(NEW, OLD);
END;
$$;


-- ============================================================
-- BROADCAST TRIGGERS
-- ============================================================

CREATE OR REPLACE TRIGGER broadcast_events
  AFTER INSERT OR UPDATE OR DELETE ON public.events
  FOR EACH ROW EXECUTE FUNCTION public.broadcast_event_changes();

CREATE OR REPLACE TRIGGER broadcast_notifications
  AFTER INSERT OR UPDATE OR DELETE ON public.notifications
  FOR EACH ROW EXECUTE FUNCTION public.broadcast_notification_changes();

CREATE OR REPLACE TRIGGER broadcast_participants
  AFTER INSERT OR UPDATE OR DELETE ON public.event_participants
  FOR EACH ROW EXECUTE FUNCTION public.broadcast_participant_changes();

CREATE OR REPLACE TRIGGER broadcast_preferred_slots
  AFTER INSERT OR UPDATE OR DELETE ON public.preferred_slots
  FOR EACH ROW EXECUTE FUNCTION public.broadcast_preferred_slots_changes();

CREATE OR REPLACE TRIGGER busy_slots_broadcast
  AFTER INSERT OR UPDATE OR DELETE ON public.busy_slots
  FOR EACH ROW EXECUTE FUNCTION public.busy_slots_broadcast_trigger();

CREATE OR REPLACE TRIGGER event_participants_broadcast
  AFTER INSERT OR UPDATE OR DELETE ON public.event_participants
  FOR EACH ROW EXECUTE FUNCTION public.event_participants_broadcast_trigger();

CREATE OR REPLACE TRIGGER notifications_broadcast
  AFTER INSERT OR UPDATE OR DELETE ON public.notifications
  FOR EACH ROW EXECUTE FUNCTION public.notifications_broadcast_trigger();

CREATE OR REPLACE TRIGGER preferred_slots_broadcast
  AFTER INSERT OR UPDATE OR DELETE ON public.preferred_slots
  FOR EACH ROW EXECUTE FUNCTION public.handle_preferred_slots_broadcast();