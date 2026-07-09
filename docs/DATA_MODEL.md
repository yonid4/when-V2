# Data Model — When. v2

All tables live in Supabase (PostgreSQL). Times are always stored in UTC. RLS policies are enforced at the database level for all user-facing operations.

---

## Table reference

### profiles
One row per user. Created on first Google OAuth login.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK, matches auth.users(id) |
| full_name | varchar(255) | From Google profile |
| avatar_url | text | From Google profile |
| email_address | varchar(255) | Unique, used for invite matching |
| timezone | varchar(50) | User preference, e.g. "America/Los_Angeles" |
| primary_calendar_provider | text | 'google' or 'microsoft' (default 'google') |
| created_at / updated_at | timestamptz | |

**v2 rule:** OAuth credentials live in `calendar_accounts.credentials` only.

---

### events
Core coordination record.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| uid | varchar(12) | Short shareable ID used in URLs |
| name | text | |
| description | text | Nullable |
| event_type | enum | meeting / social / birthday / other |
| coordinator_id | uuid | FK → profiles. Only this user can finalize/delete. Nullable — set null via ON DELETE SET NULL when the coordinator deletes their account (event stays visible to participants). |
| earliest_datetime_utc | timestamptz | Start of scheduling window |
| latest_datetime_utc | timestamptz | End of scheduling window |
| duration_minutes | int | Desired event length |
| status | enum | planning → confirmed → cancelled |
| location | text | Nullable |
| video_call_link | text | Nullable |
| allow_guest_invites | boolean | When true, all participants can invite others (not just coordinator) |
| finalized_start_time_utc | timestamptz | Set when status = confirmed |
| finalized_end_time_utc | timestamptz | Set when status = confirmed |
| calendar_event_id | text | Provider event ID (Google or Outlook) set after the finalization write to the coordinator's write calendar |
| proposals_needs_regeneration | boolean | True when busy/preferred slots change |
| proposals_last_generated_at | timestamptz | |
| created_at / updated_at / finalized_at | timestamptz | |

**Staleness rule:** Any write to `busy_slots` or `preferred_slots` for participants of an event must set `proposals_needs_regeneration = true` on that event. The proposal service checks this flag before returning cached results.

---

### event_participants
Junction table. One row per user per event.

| Column | Type | Notes |
|---|---|---|
| event_id | uuid | FK → events |
| user_id | uuid | FK → profiles |
| status | enum | invited / accepted / declined / maybe |
| rsvp_status | enum | going / maybe / not_going / pending. Nullable until set by user |
| can_invite | boolean | Whether this participant can invite others |
| joined_at | timestamptz | |

**Composite PK:** (event_id, user_id)

---

### event_invitations
Tracks invitations, including to users who don't have an account yet.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| event_id | uuid | FK → events |
| inviter_id | uuid | FK → profiles |
| invitee_id | uuid | FK → profiles. **Nullable** — null when invitee has no account yet |
| invitee_email | varchar(255) | Always populated. Used for matching on signup |
| status | enum | pending / accepted / declined |
| created_at / updated_at | timestamptz | |

**Pending invite flow:**
1. Coordinator invites `unknown@example.com` → row inserted with `invitee_id = null`
2. `unknown@example.com` creates an account
3. Auth service queries `event_invitations WHERE invitee_email = new_email AND invitee_id IS NULL`
4. For each match: set `invitee_id = new_user.id`, create notification of type `event_invitation`
5. User sees invite in their notification inbox and can accept/decline

---

### calendar_accounts
One row per connected calendar account per user. A user can connect multiple accounts across both providers.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → profiles |
| provider | varchar(50) | `google` or `microsoft`. CHECK constraint `calendar_accounts_provider_check` restricts it to these two |
| provider_email | varchar(255) | The provider account email (Gmail / Outlook) |
| provider_account_id | varchar(255) | Provider-side account ID |
| credentials | jsonb | OAuth tokens (access_token, refresh_token, expiry). The whole dict is re-persisted on rotation — Microsoft rotates the refresh token on every refresh |
| needs_reauth | boolean | Set true when a refresh fails; the UI prompts the user to reconnect |
| connected_at | timestamptz | |
| last_synced_at | timestamptz | Updated after each successful sync |

**Unique constraint:** (user_id, provider, provider_account_id) — one row per provider account per user.

---

### calendar_sources
Individual calendars within a connected account (e.g. "Work", "Personal", "Birthdays").

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| account_id | uuid | FK → calendar_accounts |
| calendar_id | varchar(255) | Provider's calendar ID string |
| calendar_name | varchar(255) | Display name |
| is_enabled | boolean | If true, include in busy slot sync |
| is_write_calendar | boolean | If true, create finalized events here. **Exactly one per user across all accounts/providers** — enforced by the `calendar_sources_single_write` trigger (clears the flag on every other source for the same user when one is set) |
| is_writable | boolean | False for read-only calendars (subscribed/imported/holiday, or shared-as-reader). Read-only calendars are still valid busy sources but can never be the write calendar — CHECK `calendar_sources_write_requires_writable` (`is_writable OR NOT is_write_calendar`) backs this |
| color | varchar(20) | For display in settings |
| created_at / updated_at | timestamptz | |

---

### busy_slots
Synced busy time blocks from Google Calendar. One row per calendar event that creates a conflict.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → auth.users(id) — **note: not profiles(id)** |
| calendar_source_id | uuid | FK → calendar_sources |
| provider_event_id | varchar(255) | Google event ID, used for upsert deduplication |
| start_time_utc | timestamptz | |
| end_time_utc | timestamptz | |
| last_synced_at | timestamptz | |
| created_at / updated_at | timestamptz | |

**Upsert key:** (provider_event_id, calendar_source_id) — re-syncing updates existing rows.

**Known inconsistency:** `user_id` references `auth.users` not `profiles`. When joining to profiles, use `auth.users.id = profiles.id` (they share the same UUID).

---

### preferred_slots
Time windows a participant has marked as preferred for a specific event.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → profiles |
| event_id | uuid | FK → events |
| start_time_utc | timestamptz | |
| end_time_utc | timestamptz | |
| created_at | timestamptz | |

**Unique constraint:** (user_id, event_id, start_time_utc, end_time_utc)

---

### proposed_times
Output of the scheduling algorithm. Cached and regenerated when stale.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| event_id | uuid | FK → events |
| start_time_utc | timestamptz | |
| end_time_utc | timestamptz | |
| conflicts | int | Number of participants with a conflict in this window |
| preferred_count | int | Number of participants who marked this window preferred |
| reasoning | text | Human-readable: "3/5 free, 2 marked as preferred" |
| rank | int | 1 = best. Unique per event |
| created_at | timestamptz | |

**Unique constraint:** (event_id, rank)

---

### proposed_time_notes
Free-text notes participants attach to a specific proposed time.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| proposed_time_id | uuid | FK → proposed_times |
| user_id | uuid | FK → profiles. The note author |
| content | text | Note body |
| created_at | timestamptz | |
| event_uid | text | Denormalized event uid (the event's short uid) |

---

### notifications
In-app inbox. One row per user per notification event.

| Column | Type | Notes |
|---|---|---|
| id | uuid | PK |
| user_id | uuid | FK → profiles. The recipient |
| event_id | uuid | FK → events. Nullable |
| notification_type | enum | See valid types below |
| title | text | Short display title |
| message | text | Full message body |
| is_read | boolean | Default false |
| action_taken | boolean | Default false. True after accept/decline |
| action_type | varchar(50) | accept / decline. Nullable |
| metadata | jsonb | Extra data (e.g. inviter name, finalized time) |
| created_at / read_at / action_at | timestamptz | |

**Valid notification types:**
- `event_invitation` — someone invited you. Has accept/decline action.
- `event_finalized` — coordinator confirmed a time
- `event_deleted` — event was deleted
- `event_time_changed` — finalized time was updated
- `invite_accepted` — an invitee accepted your invitation

---

## Key relationships

```
profiles
  ├── calendar_accounts (1:many)
  │     └── calendar_sources (1:many)
  │           └── busy_slots (1:many)
  │
  ├── events [as coordinator] (1:many)
  │
  ├── event_participants (many:many with events)
  │
  ├── event_invitations [as inviter or invitee] (1:many)
  │
  ├── preferred_slots (1:many, scoped to event)
  │
  └── notifications (1:many)

events
  ├── event_participants (1:many)
  ├── event_invitations (1:many)
  ├── busy_slots (via participants — no direct FK)
  ├── preferred_slots (1:many)
  ├── proposed_times (1:many)
  │     └── proposed_time_notes (1:many)
  └── notifications (1:many)
```

---

## RLS policy intent (implement in Supabase dashboard)

| Table | Read | Write |
|---|---|---|
| profiles | Own row only | Own row only |
| events | Coordinator or participant | Coordinator only (except status updates) |
| event_participants | All participants of the event | Coordinator adds/removes anyone; a participant may delete (leave) their own row; self-update limited to `rsvp_status` (column-level grant + WITH CHECK own row); `can_invite` changes via backend service role after coordinator check |
| event_invitations | Inviter or invitee | Coordinator or can_invite participant |
| calendar_accounts | Own rows only | Own rows only |
| calendar_sources | Own rows (via account) | Own rows only |
| busy_slots | Own rows only | Service role only (written by sync) |
| preferred_slots | All participants of the event | Own rows only |
| proposed_times | All participants of the event | Service role only (written by algorithm) |
| proposed_time_notes | Participants of the event | Author writes own notes (via backend) |
| notifications | Own rows only | Service role only (written by notification service) |

### Realtime broadcasts (`realtime.messages`)

DB triggers publish broadcast payloads into `realtime.messages`. Its RLS allows reads only through topic-scoped SELECT policies — there is no INSERT policy, so clients cannot send broadcasts:

| Topic pattern | Readable by |
|---|---|
| `event:<id>:participants` | Event coordinator or participant |
| `event:<id>:preferred_slots` | Event coordinator or participant |
| `user:<uid>:busy_slots` | That user only |
| `user:<uid>:notifications` | That user only |

The frontend does not consume broadcasts; it subscribes via `postgres_changes` (governed by the per-table policies above) and presence.
