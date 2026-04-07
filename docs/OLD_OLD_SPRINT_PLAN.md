# Sprint Plan — When. v2

Estimated total: ~4–5 weeks of focused development.
Each sprint should be fully working before the next begins — no partial features carried forward.

---

## Sprint 1 — Project foundation & auth (~3–4 days) ✅ DONE

**Goal:** Both servers run locally. Google login works end-to-end. JWT stored. Protected routes redirect correctly.

### Backend
- [x] Scaffold FastAPI project with folder structure from ARCHITECTURE.md
- [x] pydantic-settings config loading from .env
- [x] Supabase anon + service client singletons
- [x] `GET /auth/google` — redirect to Google OAuth consent
- [x] `GET /auth/google/callback` — exchange code, upsert profile, upsert calendar_accounts (Google tokens), check pending invites, issue JWT, redirect to frontend
- [x] `GET /auth/me` — return current user from JWT
- [x] `get_current_user` FastAPI dependency (uses service_client to bypass RLS)

### Frontend
- [x] Scaffold Next.js 14 (App Router) + TypeScript + Tailwind + shadcn/ui
- [x] Install and configure TanStack Query (QueryClientProvider in root layout)
- [x] Install and configure Zustand (authStore)
- [x] Next.js catch-all proxy route (`/api/[...path]/route.ts`)
- [x] Landing page with "Sign in with Google" button
- [x] `/auth/callback` page: reads token from URL, stores in localStorage, sets authStore, redirects to /dashboard
- [x] `middleware.ts`: redirect to `/` if no JWT on protected routes
- [x] `lib/api.ts`: base fetch wrapper that attaches Authorization header, handles 401

### Notes
- Google tokens (access + refresh) stored in `calendar_accounts`, not `profiles`
- `profiles.id` is a FK to `auth.users.id` — auth user created via `admin.create_user()` before profile upsert
- `on_auth_user_created` trigger must NOT exist on `auth.users` (causes DB error) — profile insert handled by backend directly
- `profiles` uses `email_address` (not `email`); `event_invitations` uses `invitee_email` and `inviter_id`
- `notification_type_enum` includes `invite_accepted`; `rsvp_status_enum` includes `pending`

### Done when
Google login flow completes, JWT is in localStorage, `/dashboard` is accessible, `/` redirects away from dashboard if logged out.

---

## Sprint 2 — Events CRUD & dashboard (~3–4 days)

**Goal:** Users can create, view, edit, and delete events. Dashboard lists their events.

### Backend
- [ ] Pydantic models: EventCreate, EventUpdate, EventResponse
- [ ] `POST /api/events` — create, generate 12-char UID, add creator as participant with status=accepted
- [ ] `GET /api/events` — list events where user is coordinator or participant
- [ ] `GET /api/events/{uid}` — full event detail
- [ ] `PUT /api/events/{uid}` — update (coordinator only), set proposals_needs_regeneration=true if window changes
- [ ] `DELETE /api/events/{uid}` — delete (coordinator only), send event_deleted notifications

### Frontend
- [ ] `types/index.ts`: Event, Participant, Notification TypeScript interfaces
- [ ] `hooks/useEvent.ts`: useEvents(), useEvent(uid), useCreateEvent(), useUpdateEvent(), useDeleteEvent()
- [ ] Dashboard page (server component): fetch event list server-side, render EventCard components
- [ ] EventCard component: name, status badge, participant count, date window, coordinator indicator
- [ ] Create event form (client component, multi-step): step 1 = details (name, type, description, location, video link), step 2 = window + duration, step 3 = confirm
- [ ] Event detail page shell (server component): fetches event SSR, passes to client islands
- [ ] Edit event modal (coordinator only)
- [ ] Delete event with confirmation dialog

### Done when
Full event lifecycle works. Dashboard shows events. Event detail page renders with SSR data.

---

## Sprint 3 — Participants, invitations & notifications (~4–5 days)

**Goal:** Inviting users works (existing and new). Notification inbox works with real-time updates.

### Backend
- [ ] `POST /api/events/{uid}/invite` — if user exists: create event_invitation + notification; if not: store with invitee_id=null
- [ ] `PUT /api/invitations/{id}/respond` — accept: add to event_participants; decline: update status
- [ ] `PUT /api/events/{uid}/participants/{user_id}/rsvp` — update rsvp_status (self only)
- [ ] `PUT /api/events/{uid}/participants/{user_id}/permissions` — toggle can_invite (coordinator only)
- [ ] `DELETE /api/events/{uid}/participants/{user_id}` — remove (coordinator, or self-removal)
- [ ] `GET /api/notifications` — paginated, sorted by created_at DESC
- [ ] `POST /api/notifications/{id}/read` — mark as read
- [ ] `POST /api/notifications/{id}/action` — accept/decline from notification

### Frontend
- [ ] `hooks/useParticipants.ts`, `hooks/useInvitations.ts`, `hooks/useNotifications.ts`
- [ ] ParticipantList component: avatar, name, RSVP badge, remove button (coordinator), can_invite toggle
- [ ] InviteInput component: email field, submit, show pending invites list
- [ ] NotificationBell component: bell icon + unread badge (from notificationStore)
- [ ] NotificationList dropdown: list of notifications with accept/decline inline actions
- [ ] Supabase real-time subscription for notifications INSERT → increment notificationStore.unreadCount
- [ ] RSVP selector on event page (going / maybe / not going)

### Done when
Inviting an existing user sends them a notification. Accepting adds them to the event. Notification bell updates in real-time.

---

## Sprint 4 — Calendar integration & busy slot sync (~4–5 days)

**Goal:** Users can connect Google Calendar, select which calendars to sync, and busy slots appear on the event page.

### Backend
- [ ] Google OAuth for calendar (separate scope from login — needs calendar.readonly + calendar.events)
- [ ] `GET /api/calendar-accounts` — list connected accounts with their sources
- [ ] `POST /api/calendar-accounts` — connect a new Google account (OAuth flow)
- [ ] `DELETE /api/calendar-accounts/{id}` — disconnect, cascade delete sources + busy slots
- [ ] `PUT /api/calendar-sources/{id}` — toggle is_enabled, toggle is_write_calendar
- [ ] Sync service: fetch freebusy from Google Calendar API for a date range, upsert busy_slots
- [ ] `POST /api/events/{uid}/sync` — manual sync for event's date range, all participants
- [ ] `GET /api/events/{uid}/busy-slots` — return merged busy slots for all participants
- [ ] APScheduler job: auto-sync all users with connected calendars every hour

### Frontend
- [ ] `hooks/useCalendarAccounts.ts`
- [ ] Settings page: list connected accounts, calendar source toggles, write calendar selector, disconnect button, timezone selector
- [ ] Sync button on event page: triggers manual sync, shows last_synced_at timestamp, loading state

### Done when
User connects Google Calendar, selects calendars, syncs, and sees red busy blocks on event page.

---

## Sprint 5 — Availability grid & scheduling algorithm (~5–6 days)

**Goal:** Participants can mark preferred slots. Algorithm generates ranked proposals with reasoning.

### Backend — algorithm
- [ ] `proposal_service.py`: slot generator (30-min sliding window across event range)
- [ ] Conflict scorer: for each window, count participants with overlapping busy_slots
- [ ] Preference scorer: for each window, count participants with overlapping preferred_slots
- [ ] Reasoning builder: "X/Y participants free, Z marked as preferred"
- [ ] Ranker: sort by conflicts ASC then preferred_count DESC, take top 5
- [ ] `POST /api/events/{uid}/proposals` — return cached if fresh, else run algorithm + cache
- [ ] `POST /api/events/{uid}/proposals/refresh` — force regenerate regardless of cache
- [ ] `POST /api/events/{uid}/preferred-slots` — save, set proposals_needs_regeneration=true
- [ ] `GET /api/events/{uid}/preferred-slots` — own slots for current user
- [ ] `DELETE /api/events/{uid}/preferred-slots/{slot_id}`

### Frontend — availability grid
- [ ] `hooks/useProposals.ts`, `hooks/usePreferredSlots.ts`
- [ ] AvailabilityGrid component: week-view calendar spanning event window, 30-min time rows
- [ ] Red overlay: busy slots for current user
- [ ] Green overlay: preferred slots (own = solid, others = lighter tint)
- [ ] Blue overlay: proposed time windows
- [ ] Click/drag interaction to mark preferred slots (optimistic update)
- [ ] ProposalPanel: list top 5 proposals with rank, conflict count, reasoning text, "Select this time" button
- [ ] Real-time: Supabase subscription on preferred_slots → invalidate proposals + grid

### Done when
User can drag to mark preferred times. Algorithm returns ranked proposals with human-readable reasoning. Grid shows all three overlay types.

---

## Sprint 6 — Event finalization & Google Calendar write (~3–4 days)

**Goal:** Coordinator can finalize a time. Creates a real Google Calendar event. All participants are notified.

### Backend
- [ ] `POST /api/events/{uid}/finalize` — coordinator picks a proposed_time_id
  - Create Google Calendar event via write calendar
  - Add all accepted participants as attendees
  - Update event: status=confirmed, finalized_start/end, google_calendar_event_id
  - Send event_finalized notification to all participants
- [ ] `GET /api/events/{uid}/finalize/status`

### Frontend
- [ ] `hooks/useFinalize.ts`
- [ ] FinalizeButton component (coordinator only): opens confirm modal showing selected time
- [ ] Confirmed event state: display finalized time prominently at top of page, disable grid editing, show "Added to your Google Calendar" indicator
- [ ] Real-time: Supabase subscription on event status change → all participants see confirmed state live

### Done when
Coordinator finalizes. A real Google Calendar event appears in attendees' calendars. All participants see the confirmed state in real-time.

---

## Sprint 7 — Polish, performance & real-time completion (~3–4 days)

**Goal:** App feels fast. All real-time updates work. No rough edges.

### Performance
- [ ] Audit event page: consolidate all SSR data fetches into a single parallel Promise.all — page must arrive fully populated
- [ ] Optimistic updates on preferred slot save (immediate grid update, sync in background)
- [ ] Dashboard: confirm SSR renders event list with no loading state on first paint

### Real-time completion
- [ ] Wire remaining Supabase subscriptions: busy_slots changes, participant joins, event status changes
- [ ] Presence indicator: show which participants are currently on the event page (Supabase presence)

### UX & polish
- [ ] Navbar with logout button (calls `authStore.clearAuth()`, redirects to `/`)
- [ ] Empty states: dashboard (no events yet), notifications (inbox empty), event page (no proposals yet, no preferred slots yet)
- [ ] Error boundaries + toast notifications for failed API calls
- [ ] Consistent timezone display — all times in user's local timezone via `lib/dates.ts`
- [ ] Mobile responsiveness pass on all pages
- [ ] 404 page for unknown event UIDs
- [ ] Loading skeletons for any remaining async islands

### Cleanup
- [ ] Remove legacy columns from profiles (google_auth_token, microsoft_auth_token, google_calendar_id)
- [ ] Audit all service_client usages — confirm none are used where anon_client should be used
- [ ] Remove any dead code from v1 references

### Done when
Page loads feel instant. Real-time updates work across all event page interactions. No visible loading states on initial renders.