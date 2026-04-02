# Sprint Plan — When. v2

Estimated total: ~4–5 weeks of focused development.
Each sprint should be fully working before the next begins — no partial features carried forward.

---

## Required reading before every sprint

| Document | Why |
|---|---|
| `docs/LESSONS_LEARNED.md` | Implementation discoveries and corrections — takes priority over all other docs |
| `docs/CLAUDE.md` | Project rules, patterns, what not to do |
| `docs/STITCH_DESIGN.md` | Design file map, icon replacements, CSS variable reference |

---

## Sprint 1 — Project foundation & auth ✅ DONE

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

### Key discoveries → see `docs/LESSONS_LEARNED.md` Sprint 1 section

> Tests written and passing — see `backend/tests/test_auth.py` and `frontend/__tests__/auth/`

---

## Sprint 2 — Events CRUD & dashboard ✅ DONE

**Design references:** `docs/STITCH_DESIGN.md` → Dashboard (screenshot-based spec), Create Event Steps 1–3, Event Detail sections

**Goal:** Users can create, view, edit, and delete events. Dashboard lists their events.

### Backend
- [ ] Pydantic models: EventCreate, EventUpdate, EventResponse
- [ ] `POST /api/events` — create, generate 12-char UID, add creator as participant with status=accepted
- [ ] `GET /api/events` — list events where user is coordinator or participant
- [ ] `GET /api/events/{uid}` — full event detail
- [ ] `PUT /api/events/{uid}` — update (coordinator only), set proposals_needs_regeneration=true if window changes
- [ ] `DELETE /api/events/{uid}` — delete (coordinator only), send event_deleted notifications

### Frontend
- [ ] `types/index.ts` — Event, Participant, Notification TypeScript interfaces
- [ ] `hooks/useEvent.ts` — useEvents(), useEvent(uid), useCreateEvent(), useUpdateEvent(), useDeleteEvent()
- [ ] Dashboard page (server component) — fetch event list server-side, render EventCard components
- [ ] EventCard component — match `design/dashboard.html`
- [ ] Create event form (multi-step) — match `design/create-step1.html`, `create-step2.html`, `create-step3.html`
- [ ] Event detail page shell (server component) — fetch event SSR, match `design/event-detail.html` layout
- [ ] Edit event modal (coordinator only)
- [ ] Delete event with confirmation dialog

### Done when
Full event lifecycle works. Dashboard shows events. Event detail page renders with SSR data.

> Tests written and passing — see `backend/tests/test_events.py` and `frontend/__tests__/EventCard.test.tsx`, `CreateEventForm.test.tsx`, `useEvent.test.ts`

---

## Sprint 3 — Participants, invitations & notifications

**Design references:** `docs/STITCH_DESIGN.md` → Event Detail (right panel: participants section), Notification Bell

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
- [ ] ParticipantList component — match `design/event-detail.html` participants section
- [ ] InviteInput component — email field + submit, match `design/event-detail.html` actions section
- [ ] NotificationBell component — match `docs/STITCH_DESIGN.md` Notification Bell spec
- [ ] NotificationList dropdown — accept/decline inline actions
- [ ] Supabase real-time subscription for notifications INSERT → increment notificationStore.unreadCount
- [ ] RSVP selector on event page

### Done when
Inviting an existing user sends them a notification. Accepting adds them to the event. Notification bell updates in real-time.

---

## Sprint 4 — Calendar integration & busy slot sync

**Design references:** `docs/STITCH_DESIGN.md` → Settings page

**Goal:** Users can connect Google Calendar, select which calendars to sync, and busy slots appear on the event page.

### Backend
- [ ] Google OAuth for calendar (separate scope — needs calendar.readonly + calendar.events)
- [ ] `GET /api/calendar-accounts` — list connected accounts with their sources
- [ ] `POST /api/calendar-accounts` — connect a new Google account (OAuth flow)
- [ ] `DELETE /api/calendar-accounts/{id}` — disconnect, cascade delete sources + busy slots
- [ ] `PUT /api/calendar-sources/{id}` — toggle is_enabled, toggle is_write_calendar
- [ ] Sync service — fetch freebusy from Google Calendar API, upsert busy_slots
- [ ] `POST /api/events/{uid}/sync` — manual sync for event's date range, all participants
- [ ] `GET /api/events/{uid}/busy-slots` — return merged busy slots for all participants
- [ ] APScheduler job — auto-sync all users with connected calendars every hour

### Frontend
- [ ] `hooks/useCalendarAccounts.ts`
- [ ] Settings page — match `design/settings.html` via `docs/STITCH_DESIGN.md` Settings section
- [ ] Sync button on event page — triggers manual sync, shows last_synced_at, loading state

### Done when
User connects Google Calendar, selects calendars, syncs, and sees red busy blocks on event page.

---

## Sprint 5 — Availability grid & scheduling algorithm

**Design references:** `docs/STITCH_DESIGN.md` → Event Detail (left panel: availability grid, legend, heatmap, overlays)

**Goal:** Participants can mark preferred slots. Algorithm generates ranked proposals with reasoning.

### Backend — algorithm
- [ ] `proposal_service.py` — slot generator (30-min sliding window across event range)
- [ ] Conflict scorer — count participants with overlapping busy_slots per window
- [ ] Preference scorer — count participants with overlapping preferred_slots per window
- [ ] Reasoning builder — "X/Y participants free, Z marked as preferred"
- [ ] Ranker — sort by conflicts ASC then preferred_count DESC, take top 5
- [ ] `POST /api/events/{uid}/proposals` — return cached if fresh, else run algorithm + cache
- [ ] `POST /api/events/{uid}/proposals/refresh` — force regenerate
- [ ] `POST /api/events/{uid}/preferred-slots` — save, set proposals_needs_regeneration=true
- [ ] `GET /api/events/{uid}/preferred-slots` — own slots for current user
- [ ] `DELETE /api/events/{uid}/preferred-slots/{slot_id}`

### Frontend — availability grid
- [ ] `hooks/useProposals.ts`, `hooks/usePreferredSlots.ts`
- [ ] AvailabilityGrid component — match `design/event-detail.html` grid exactly: day columns, 30-min rows, color overlays (red=busy, green=preferred, pink=proposed, dark=conflict), intensity heatmap legend
- [ ] Click/drag to mark preferred slots (optimistic update)
- [ ] ProposalPanel — match `design/event-detail.html` Top Proposals section
- [ ] Real-time: Supabase subscription on preferred_slots → invalidate proposals + grid

### Done when
User can drag to mark preferred times. Algorithm returns ranked proposals with reasoning. Grid shows all overlay types.

---

## Sprint 6 — Event finalization & Google Calendar write

**Design references:** `docs/STITCH_DESIGN.md` → Event Detail (right panel: Top Proposals Select button, confirmed state)

**Goal:** Coordinator finalizes a time. Creates a real Google Calendar event. All participants notified.

### Backend
- [ ] `POST /api/events/{uid}/finalize` — coordinator picks a proposed_time_id, creates Google Calendar event via write calendar, adds all accepted participants as attendees, updates event status=confirmed + finalized times + google_calendar_event_id, sends event_finalized notifications
- [ ] `GET /api/events/{uid}/finalize/status`

### Frontend
- [ ] `hooks/useFinalize.ts`
- [ ] FinalizeButton / Select button (coordinator only) — confirm modal with selected time
- [ ] Confirmed event state — finalized time prominent, grid editing disabled, "Added to Google Calendar" indicator
- [ ] Real-time: Supabase subscription on event status change → all participants see confirmed state live

### Done when
Coordinator finalizes. Google Calendar event appears in attendees' calendars. All participants see confirmed state in real-time.

---

## Sprint 7 — Polish, performance & real-time completion

**Design references:** `docs/STITCH_DESIGN.md` — full review of all pages for remaining visual gaps

**Goal:** App feels fast. All real-time updates work. No rough edges.

### Performance
- [ ] Audit event page — consolidate all SSR fetches into a single parallel Promise.all, page must arrive fully populated
- [ ] Optimistic updates on preferred slot save
- [ ] Dashboard SSR — event list pre-rendered, no loading state on first paint

### Real-time completion
- [ ] Wire remaining Supabase subscriptions: busy_slots changes, participant joins, event status changes
- [ ] Presence indicator — show which participants are currently on the event page

### UX & polish
- [ ] Navbar logout button — calls `authStore.clearAuth()`, redirects to `/`
- [ ] Empty states — dashboard, notifications, event page (no proposals yet, no preferred slots yet)
- [ ] Error boundaries + toast notifications for failed API calls
- [ ] Timezone display — all times in user's local timezone via `lib/dates.ts`
- [ ] Mobile responsiveness pass on all pages
- [ ] 404 page for unknown event UIDs
- [ ] Loading skeletons for remaining async islands

### Cleanup
- [ ] Remove legacy columns from profiles (google_auth_token, microsoft_auth_token, google_calendar_id)
- [ ] Audit all service_client usages — confirm none where anon_client should be used
- [ ] Remove any dead code

### Done when
Page loads feel instant. Real-time updates work across all interactions. No visible loading states on initial renders.