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
- [x] Pydantic models: EventCreate, EventUpdate, EventResponse
- [x] `POST /api/events` — create, generate 12-char UID, add creator as participant with status=accepted
- [x] `GET /api/events` — list events where user is coordinator or participant
- [x] `GET /api/events/{uid}` — full event detail
- [x] `PUT /api/events/{uid}` — update (coordinator only), set proposals_needs_regeneration=true if window changes
- [x] `DELETE /api/events/{uid}` — delete (coordinator only), send event_deleted notifications

### Frontend
- [x] `types/index.ts` — Event, Participant, Notification TypeScript interfaces
- [x] `hooks/useEvent.ts` — useEvents(), useEvent(uid), useCreateEvent(), useUpdateEvent(), useDeleteEvent()
- [x] Dashboard page (server component) — fetch event list server-side, render EventCard components
- [x] EventCard component — match `docs/STITCH_DESIGN.md` Dashboard spec (screenshot-based, no HTML file)
- [x] Create event form (multi-step) — match `design/create-step1.html`, `create-step2.html`, `create-step3.html`
- [x] Event detail page shell (server component) — fetch event SSR, match `design/event-detail.html` layout
- [x] Edit event modal (coordinator only)
- [x] Delete event with confirmation dialog

### Done when
Full event lifecycle works. Dashboard shows events. Event detail page renders with SSR data.

> Tests written and passing — see `backend/tests/test_events.py` and `frontend/__tests__/EventCard.test.tsx`, `CreateEventForm.test.tsx`, `useEvent.test.ts`

---

## Sprint 3 — Participants, invitations & notifications ✅ DONE

**Design references:** `docs/STITCH_DESIGN.md` → Event Detail (right panel: participants section), Notification Bell

**Goal:** Inviting users works (existing and new). Notification inbox works with real-time updates.

### Backend
- [x] `POST /api/events/{uid}/invite` — if user exists: create event_invitation + notification; if not: store with invitee_id=null
- [x] `PUT /api/invitations/{id}/respond` — accept: add to event_participants; decline: update status
- [x] `PUT /api/events/{uid}/participants/{user_id}/rsvp` — update rsvp_status (self only)
- [x] `PUT /api/events/{uid}/participants/{user_id}/permissions` — toggle can_invite (coordinator only)
- [x] `DELETE /api/events/{uid}/participants/{user_id}` — remove (coordinator, or self-removal)
- [x] `GET /api/notifications` — paginated, sorted by created_at DESC
- [x] `POST /api/notifications/{id}/read` — mark as read
- [x] `POST /api/notifications/{id}/action` — accept/decline from notification

### Frontend
- [x] `hooks/useParticipants.ts`, `hooks/useInvitations.ts`, `hooks/useNotifications.ts`
- [x] ParticipantList component — match `design/event-detail.html` participants section
- [x] InviteInput component — email field + submit, match `design/event-detail.html` actions section
- [x] NotificationBell component — match `docs/STITCH_DESIGN.md` Notification Bell spec
- [x] NotificationList dropdown — accept/decline inline actions
- [x] Supabase real-time subscription for notifications INSERT → increment notificationStore.unreadCount
- [x] RSVP selector on event page

### Key discoveries → see `docs/LESSONS_LEARNED.md` Sprint 3 section

> Tests written and passing — see `backend/tests/test_participants.py`, `test_invitations.py`, `test_notifications.py` and `frontend/__tests__/sprint3/`

---

## Sprint 4 — Calendar integration & busy slot sync ✅ DONE

**Design references:** `docs/STITCH_DESIGN.md` → Settings page

**Goal:** Users can connect Google Calendar, select which calendars to sync, and busy slots appear on the event page.

### Backend
- [x] Google OAuth for calendar (separate scope — needs calendar.readonly + calendar.events)
- [x] `GET /api/calendar-accounts` — list connected accounts with their sources
- [x] `GET /api/calendar-accounts/connect` + `GET /api/calendar-accounts/callback` — Google OAuth flow (state carries user_id)
- [x] `DELETE /api/calendar-accounts/{id}` — disconnect, cascade delete sources + busy slots
- [x] `PATCH /api/calendar-sources/{id}` — toggle is_enabled, toggle is_write_calendar (exclusive per user via RPC)
- [x] Sync service — fetch events from Google Calendar API, upsert busy_slots (dedup on provider_event_id + calendar_source_id); delete stale slots whose provider_event_id no longer appears in Google's response or is returned as `status=cancelled` (scoped to `calendar_source_id`, upper-bounded by `end_time_utc < time_max_iso`)
- [x] `POST /api/busy-slots/sync` — manual sync for current user
- [x] `POST /api/busy-slots/sync/event/{uid}` — coordinator-only participant sync
- [x] `GET /api/busy-slots` — current user's busy slots
- [x] `GET /api/busy-slots/event/{uid}` — all participant busy slots for an event
- [x] APScheduler job — auto-sync all users with connected calendars every hour (lifespan-based BackgroundScheduler)

### Frontend
- [x] `hooks/useCalendarAccounts.ts` — useCalendarAccounts, useDisconnectCalendarAccount, useUpdateCalendarSource
- [x] `hooks/useBusySlots.ts` — useEventBusySlots, useSyncCalendar, useSyncMyCalendar
- [x] Settings page — match `design/settings.html`, account list with source toggles, disconnect, sync
- [x] Sync button on event page (EventDetailClient) — triggers `useSyncCalendar`, loading spinner state
- [x] AvailabilityGrid wired with `busySlots` prop from `useEventBusySlots`
- [x] Shared `Navbar` component (`components/layout/Navbar.tsx`) with "When." wordmark, `<NotificationBell />`, and user profile avatar with dropdown (Settings, Log out)
- [x] Profile avatar dropdown — Settings link + logout (calls `authStore.clearAuth()`, redirects to `/`)

### Key discoveries → see `docs/LESSONS_LEARNED.md` Sprint 4 section

> Tests written and passing — see `backend/tests/test_calendar.py`, `test_sync.py` and `frontend/__tests__/sprint4/`

---

## Sprint 4 (Post) — Auth, Calendar & UI Rework ✅ DONE

**Goal:** Fix calendar OAuth flow, separate login from calendar scopes, enforce calendar requirement before joining events, consolidate navbar across all authenticated pages, and fix several UX bugs discovered during manual testing.

### Backend
- [x] `GET /api/calendar-accounts/connect-url` — returns `{ url }` as JSON instead of redirecting (fixes 403 caused by missing Authorization header on browser navigation)
- [x] Separated login OAuth scopes (identity only) from calendar OAuth scopes (`calendar.readonly`, `calendar.events`)
- [x] Removed `_upsert_calendar_account` call from login callback — calendar accounts created only via explicit connect flow
- [x] Added try/except with `exc_info=True` logging around `connect_google_account` in calendar callback
- [x] Removed `flow.oauth2session.scope = None` hack — scopes passed explicitly to `Flow.from_client_config`
- [x] Added `GOOGLE_CALENDAR_REDIRECT_URI` to `.env` and `.env.example`
- [x] `respond_to_invitation` now checks for connected `calendar_sources` before accepting — raises `422 calendar_required` if none found

### Frontend
- [x] Created `components/layout/Navbar.tsx` — shared navbar with wordmark, bell, and avatar dropdown
- [x] Replaced inline headers on dashboard, settings, and event detail pages with `<Navbar />`
- [x] Connect calendar button changed from `<a href>` to `<button>` calling `useConnectCalendarAccount` hook
- [x] `NotificationList` redirects to `/settings?connect_calendar=true` when API returns `422 calendar_required`
- [x] Settings page shows dismissible banner when `connect_calendar=true` search param is present
- [x] Unread notification count initialized from fetched notification list on mount via `setCount` in `notificationStore`
- [x] Write calendar radio group added to settings page — one write calendar allowed across all accounts and sources
- [x] Create event form: participant emails collected in step 2 are sent as invitations after event creation using direct `api.post` calls (not hook-based)
- [x] Create event form: step 2 date/time fields initialize with defaults on first open (start = today, end = 7 days from today, start time = 09:00, end time = 17:00)
- [x] Create event form: date range validation — start date cannot be in the past, end date cannot be before start date, end time must be after start time when same day
- [x] Accept invitation redirects to `/events/{event_uid}` after success — decline stays on current page

### Done when
Calendar connect flow works end-to-end. Login shows identity-only consent. Navbar with bell and avatar appears on all authenticated pages. Users without a connected calendar are gated from joining events. All UX bugs from manual testing resolved.

---

## Sprint 4 (Post-2) — Event Detail Rework & AvailabilityGrid ✅ DONE

**Goal:** Overhaul the event detail page to match the updated design: full-height two-column layout, enriched edit modal, AvailabilityGrid driven by real event time window, and server-side simplification by moving coordinator/user resolution to the client via `authStore`.

### Backend
- [x] `GET /api/busy-slots/event/{uid}` — fetch event row now selects `earliest_datetime_utc` and `latest_datetime_utc`; busy slots filtered server-side to only those overlapping the event window (`.lt("start_time_utc", latest).gt("end_time_utc", earliest)`); returns 404 if event not found (was previously returning empty list)

### Frontend
- [x] `types/index.ts` — added `allow_guest_invites: boolean` to `Event` interface
- [x] `app/events/[uid]/page.tsx` — removed server-side `getCurrentUserId` fetch and `isCoordinator` derivation; page now only fetches the event and passes it to `EventDetailClient`
- [x] `app/events/[uid]/EventDetailClient.tsx` — complete rework
- [x] `app/events/[uid]/editEventUtils.ts` — extracted edit schema, helpers, and diff computation
- [x] `app/events/new/page.tsx` — Step 2 now collects `start_time` and `end_time`
- [x] `components/layout/Navbar.tsx` — full width, no max-w constraint
- [x] `AvailabilityGrid` — driven by real event time window, 7-day week view with navigation

### Done when
Event detail page renders in full-height two-column layout. Edit modal covers all editable fields. AvailabilityGrid shows hours within the event time window. Create event form captures start/end time of day. Busy slot API filters to event window only.

---

## Sprint 5 — Availability Grid, Preferred Slots & Busy Slot Rendering

**Design references:**
- `design/event-detail.html` + `design/event-detail.png` — view mode grid with all overlay types
- `design/event-detail-edit.html` + `design/event-detail-edit.png` — edit mode with pending slot and action bar

**Goal:** Busy slots render on the grid. Participants can mark preferred slots using Outlook-style drag editing. Grid shows all overlay types correctly.

> Complete parts in order. Do not start the next part until the current part is fully working and tested.

---

### Part A — Busy slot rendering on the grid ✅ DONE

**Goal:** Synced calendar events appear as colored blocks on the AvailabilityGrid.

#### Frontend
- [x] Create `frontend/lib/gridUtils.ts` with a pure `getSlotsForCell` helper function
- [x] Map each `busySlot` to the correct day column and 30-min half-rows it spans using UTC overlap detection
- [x] Cell rendering rules based on `busyCount` and `preferredCount` per cell:
  - **Busy only** (busyCount > 0, preferredCount === 0): solid red block, intensity scales with busyCount (1: `bg-error/30`, 2: `bg-error/55`, 3+: `bg-error/80`), time range label inside
  - **Preferred only** (preferredCount > 0, busyCount === 0): solid green block, intensity scales with preferredCount (1: `bg-secondary/30`, 2: `bg-secondary/55`, 3+: `bg-secondary/80`), time range label inside
  - **Conflict** (busyCount > 0 AND preferredCount > 0): split cell vertically — left half red at busy intensity, right half green at preferred intensity, "CONFLICT" label overlaid centered on top of both halves
  - **Empty**: render as before
- [x] Busy and conflict cells are never interactive — cursor `default`, no hover in edit mode
- [x] Pass `preferredSlots={[]}` to `AvailabilityGrid` for now — Part B will wire real data

#### Done when
After syncing calendar, busy slots appear as red blocks on the correct days and times. Intensity scales correctly. Conflict (busy + preferred overlap) shows split cell with CONFLICT label. Heatmap legend matches cell intensity.

> Tests: `frontend/__tests__/sprint5/gridUtils.test.ts` — `getSlotsForCell` pure function only (no React rendering)

---

### Part B — Preferred slots (backend + frontend) ✅ DONE

**Goal:** Users can save and retrieve their preferred time slots for an event.

#### Backend
- [x] `POST /api/events/{uid}/preferred-slots` — save a preferred slot for current user; set `proposals_needs_regeneration=true` on the event; body: `{ start_time_utc, end_time_utc }`
- [x] `GET /api/events/{uid}/preferred-slots` — return only the current user's preferred slots for this event
- [x] `DELETE /api/events/{uid}/preferred-slots/{slot_id}` — delete a preferred slot (own slots only)
- [x] All three endpoints return 403 if the user is not a participant or coordinator

#### Frontend
- [x] `hooks/usePreferredSlots.ts` — `usePreferredSlots(uid)`, `useSavePreferredSlot(uid)`, `useDeletePreferredSlot(uid)`
- [x] Pass real `preferredSlots` data from `usePreferredSlots` into `AvailabilityGrid` — replacing the `[]` placeholder from Part A
- [x] Confirmed preferred slots render as solid green 30-min half-row blocks (Part A rendering already handles this)
- [x] Conflict cells now show correctly when a preferred slot overlaps a busy slot
- [x] Supabase real-time subscription on `preferred_slots` INSERT/DELETE → invalidate `['preferred-slots', uid]` query → grid re-renders

#### Done when
User saves a preferred slot via the API. It appears as a green block on the grid immediately. If it overlaps a busy slot, a split conflict cell appears. Deleting it removes it from the grid. Real-time: a second browser tab sees the change without refreshing.

> Tests: `backend/tests/test_preferred_slots.py`, `frontend/__tests__/sprint5/usePreferredSlots.test.ts`

---

### Part C — Edit mode interaction ✅ DONE

**Design references:** `design/event-detail-edit.html` + `design/event-detail-edit.png`

**Goal:** Users enter edit mode and drag to mark preferred times. Changes are held as pending until Done or Cancel.

#### Frontend
- [x] "Edit Availability" button top-right of grid header — outlined secondary style with pencil icon
- [x] Clicking enters edit mode — button transforms to "Editing..." with pulsing terracotta dot
- [x] In edit mode: grid cells show crosshair cursor on hover (except busy and conflict cells which show `not-allowed`)
- [x] Drag interaction (within a single day column only):
  - Mousedown on a half-row starts a drag
  - Dragging up or down highlights the continuous range as a pending slot (semi-transparent green, dashed border)
  - Mouseup ends the drag — pending slot stays on screen, not yet saved
  - Only one pending slot at a time per edit session
- [x] Resize: after releasing drag, user can drag the top or bottom edge of the pending slot to expand or shrink it in 30-min increments
- [x] Merge logic: if the pending slot overlaps with an existing confirmed preferred slot on the same day, the two merge. Merged range becomes the new pending slot; original confirmed slot marked for deletion on Done.
- [x] Busy slot overlap: dragging over a busy slot is allowed — no blocking
- [x] Floating action bar always visible while in edit mode, anchored to bottom of grid card
- [x] Cancel: discards pending slot, restores original confirmed slots, exits edit mode — no API call
- [x] Done: calls DELETE for merged slots, POST for new slot, exits on success, stays in edit mode on failure
- [x] Busy/preferred overlays clipped to non-conflict segments via `subtractConflicts()` — no background bleed under conflict blocks
- [x] Every slot overlay has 2px vertical gap so rounded corners remain visible between adjacent blocks
- [x] Slot labels show for segments ≥ 30 minutes, centered to segment height

#### Done when
User enters edit mode, drags to select a time range, sees dashed green pending block, resizes it, clicks Done — slot appears as solid green confirmed block. Cancel discards. Merge works. Conflict cells appear cleanly with no background bleed from adjacent busy/preferred blocks.

> Tests: `frontend/__tests__/sprint5/EditMode.test.tsx` — enter/exit edit mode, drag creates pending slot, Cancel discards, Done saves, merge logic (component tests skipped due to jsdom hang; pure function tests in `editModeUtils.test.ts` pass fully)

---

### Part D — Click to delete confirmed preferred slots ✅ DONE

**Goal:** Users can remove their own confirmed preferred slots directly from the grid in both view mode and edit mode.

#### Frontend
- [x] Clicking a confirmed preferred slot owned by the current user shows an inline "Remove this slot?" confirmation with Cancel and Remove buttons
- [x] Other participants' preferred slots have no click handler — not interactive
- [x] Two-layer overlay architecture: merged display overlays (pointer-events: none) for correct intensity rendering, plus a separate transparent click overlay (z-index: 25, pointer-events: auto) covering the full slot geometry for each own slot
- [x] Click overlay covers the full slot height including any conflict-overlapping portion — clicking the conflict zone of an own slot still triggers the confirmation
- [x] `deletingSlotId: string | null` state in `EventDetailClient` tracks which slot is awaiting confirmation
- [x] Pressing Escape dismisses the confirmation (keydown listener attached/removed with useEffect)
- [x] Clicking elsewhere on the grid column dismisses the confirmation (onClick on column div)
- [x] **View mode confirm:** calls `useDeletePreferredSlot` immediately — slot removed from DB
- [x] **Edit mode confirm:** adds slot to `slotsToDelete` + removes from `displayedPreferredSlots` optimistically — slot physically deleted on Done (same flow as merge-replaced slots)
- [x] Slots already in `slotsToDelete` are excluded from the click overlay — no ghost clickable region over a visually-removed slot

#### Done when
User clicks their own green preferred slot in view mode → sees "Remove this slot?" → confirms → slot disappears. Same in edit mode: confirmation appears, confirm marks it pending deletion, Done commits. Clicking conflict zone of own slot works. Escape and clicking away dismiss without action.

---

### Part E — Edit mode hardening & density rendering ✅ DONE

**Goal:** Fix correctness bugs in edit mode merge logic and improve preferred slot density visualization.

#### Frontend
- [x] `runMergeCheck` only receives own slots — `handleDocumentMouseUp` filters to `user_id === user?.id` before calling it at both drag and resize call sites
- [x] `runMergeCheck` re-appends foreign slots to `displayedPreferredSlots` so other participants' slots remain visible in edit mode
- [x] `handleDone` uses `Promise.allSettled` for batched deletes — surfaces a single error if any delete fails, never crashes on a stale foreign id
- [x] Edit-mode own-slot interactive overlay gated on `isEditMode` — clicking preferred slots in view mode does nothing
- [x] Other participants' preferred slots visible in edit mode as read-only (no click handler, no pointer events)
- [x] `computeMerge` overlap condition changed to `<=`/`>=` so slots touching at a single boundary point merge into one continuous block
- [x] Own slot dot indicator rendered as a separate pass per DB slot (`own-dot-{id}`) — visible even when the slot partially overlaps a merged segment
- [x] Preferred slot color density computed per region via `buildCountedSegments` — only splits at density bucket boundaries (1–2, 3–4, 5–6, 7+); adjacent same-bucket segments merge into one visual block
- [x] `editModeUtils.test.ts` updated to reflect new adjacent-boundary merge semantics

#### Done when
Edit mode merges only own slots. Foreign slots remain visible. Done completes without crash. Color intensity accurately reflects participant overlap per region, not per merged block.

---

## Sprint 6 — Proposals & Event Finalization

**Design references:** `docs/STITCH_DESIGN.md` → Event Detail (right panel: Top Proposals Select button, confirmed state)

**Goal:** Algorithm generates ranked time proposals. Coordinator finalizes a time. Google Calendar event created. All participants notified.

> Complete parts in order. Discuss algorithm design with the developer before writing any code for Part A.

---

### Part A — Scheduling algorithm & proposals ✅ DONE

**Goal:** Backend generates ranked time proposals. Frontend displays them in the ProposalPanel.

#### Backend
- [x] `proposal_service.py`:
  - Slot generator — 30-min sliding window across the full event scheduling window
  - Conflict scorer — for each window, count participants with overlapping `busy_slots`
  - Preference scorer — for each window, count participants with overlapping `preferred_slots`
  - Reasoning builder — human-readable string: "X/Y participants free, Z marked as preferred"
  - Ranker — sort by `conflicts ASC` then `preferred_count DESC`, take top 5
  - Cache result in `proposed_times` table; set `proposals_last_generated_at`
- [x] `POST /api/events/{uid}/proposals` — return cached proposals if `proposals_needs_regeneration=false` and cache exists; otherwise run algorithm and cache
- [x] `POST /api/events/{uid}/proposals/refresh` — force regenerate regardless of cache state

#### Frontend
- [x] `hooks/useProposals.ts` — `useProposals(uid, enabled)`, `useRefreshProposals(uid)`
- [x] Wire ProposalPanel — replace the current placeholder with real ranked proposals from the API
- [x] Each proposal card shows: day + time, reasoning string ("X/Y participants free, Z marked as preferred"), "Select" button (coordinator only)
- [x] "View Proposed Times" CTA button triggers `useProposals` fetch and scrolls to ProposalPanel
- [x] If `proposals_needs_regeneration=true`, show a "Results may be outdated — Regenerate" prompt above the list
- [x] Real-time: `preferred_slots` INSERT/DELETE → ProposalPanel shows regenerate prompt

#### Done when
After participants mark preferred slots, coordinator clicks "View Proposed Times" and sees a ranked list with reasoning. Regenerate works. Proposals update prompt appears when preferred slots change.

> Tests: `backend/tests/test_proposals.py` (11 tests), `frontend/__tests__/sprint6/useProposals.test.ts` (5 tests) — all passing

---

### Part B — Event finalization ✅ DONE

**Goal:** Coordinator selects a proposal, confirms in a modal, and a real Google Calendar event is created.

#### Backend
- [x] `POST /api/events/{uid}/finalize` — coordinator only:
  - Accepts `proposed_time_id`
  - Creates a Google Calendar event on the coordinator's write calendar
  - Adds all `status=accepted` participants as attendees
  - Updates event: `status=confirmed`, `finalized_start_time_utc`, `finalized_end_time_utc`, `google_calendar_event_id`
  - Sends `event_finalized` notification to all participants
- [x] `GET /api/events/{uid}/finalize/status` — returns finalized time and Google Calendar event ID

#### Frontend
- [x] `hooks/useFinalize.ts` — `useFinalize(uid)`, `useFinalizeStatus(uid)`
- [x] "Select" button on a proposal card opens a confirm modal showing:
  - Selected time (day, date, full time range)
  - List of accepted participants who will be added as attendees
  - Optional note field
  - "Confirm & Add to Calendar" button (terracotta) and "Back" button (outlined)
- [x] On confirmation: calls `POST /api/events/{uid}/finalize`, shows loading state on button
- [x] Confirmed event state (after finalization):
  - Finalized time shown prominently at top of right panel
  - Grid editing disabled — "Edit Availability" button hidden
  - "Added to Google Calendar" indicator with calendar icon
  - All proposal "Select" buttons hidden
- [x] Real-time: Supabase subscription on `events.status` change → all participants see confirmed state live without refreshing

#### Done when
Coordinator selects a proposal, confirms in the modal, Google Calendar event appears in attendees' calendars, all participants see the confirmed time on the event page in real-time.

> Tests: `backend/tests/test_finalize.py` (7 tests), `frontend/__tests__/sprint6/useFinalize.test.ts` (3 tests) — all passing

---

### Part C — Finalize event card (full form)

**Goal:** Replace the minimal confirm modal with a full finalization card. Coordinator 
fills in all event details before creating the Google Calendar event.

#### Backend
- [x] Add `location: str | None`, `video_call_link: str | None`, `excluded_user_ids: 
      list[str]`, and `extra_emails: list[str]` to `FinalizeRequest` Pydantic model
- [x] Pass all new fields into `finalize_event()` function signature
- [x] Build attendees list: accepted participants minus excluded_user_ids + extra_emails 
      + coordinator (all by email)
- [x] Update `events.name` in DB if name differs from current event name
- [x] Include `location` in Google Calendar event body (dedicated field, omit if empty)
- [x] Build description: note + "\n\nVideo call: {video_call_link}" — omit video call 
      line if link is empty
- [x] Add `location` and `video_call_link` to `events.update(...)` payload
- [x] Add `location: str | None` and `video_call_link: str | None` columns to events 
      table if missing — check schema.sql and run migration

#### Frontend
- [x] Update `useFinalize` mutation body type to include all new fields
- [x] Update `FinalizeStatus` and `Event` types in `types/index.ts` to include 
      `location` and `video_call_link`
- [x] Remove per-proposal "Select" button from ProposalPanel — replace with single 
      "Finalize Event" button (coordinator only, hidden when event is confirmed)
- [x] Replace `FinalizeModal` with full-screen overlay `FinalizeCard` component:
  - **Event name** — text input, pre-filled from event.name, required; updates 
    both When. event and Google Calendar event title on submit
  - **Attendees** — checklist of accepted participants (display name + email), all 
    checked by default; coordinator can uncheck to exclude; plus an email input 
    field to add extra non-When. invitees (calendar only, no participant record); 
    at least one attendee must remain
  - **Proposed time** — radio card list of all proposals from useProposals; none 
    pre-selected; required
  - **Note** — textarea, optional; becomes Google Calendar description
  - **Location** — text input, optional; maps to GCal location field
  - **Video call link** — URL text input, optional; appended to GCal description 
    as "Video call: {link}"
  - "Confirm & Add to Calendar" — disabled until time selected + name non-empty; 
    loading spinner while pending
  - "Cancel" — closes card, no API call
  - Error states: 502 → "Could not create calendar event — check your calendar 
    connection"; 422 → "No write calendar configured — go to Settings to set one"
- [x] On success: close card, show confirmed state (finalized time banner, grid 
      read-only, Finalize Event button hidden)

#### Done when
Coordinator opens finalize card, sees all proposals as radio options, fills in 
name + optional fields, adds/removes attendees, picks a time, submits. Google 
Calendar event created with location and description. All included attendees 
(When. participants + extra emails) added as invitees. Confirmed state shown to 
all participants in real-time.

> Tests: update `backend/tests/test_finalize.py` and 
  `frontend/__tests__/sprint6/useFinalize.test.ts`

---

## Sprint 7 — Bug Fixes ✅ DONE

**Goal:** Fix critical bugs discovered during manual testing.

---

### Part A — Bug fixes ✅ DONE

- [x] **Accept invitation redirect** — `PUT /api/invitations/{id}/respond` now returns `{ event_uid }` on accept; frontend calls this endpoint directly from the notification accept button and redirects to `/events/{event_uid}`. Previously the notification action endpoint returned `event_uid: null` because the Supabase update response has no `events` join.
- [x] **Gmail dot normalization** — Added `normalize_email()` in `app/utils/email.py`; strips dots from the local part for `@gmail.com` only. Applied in `auth_service._upsert_profile` and `invitation_service.invite_by_email` so `john.doe@gmail.com` and `johndoe@gmail.com` are treated as the same address throughout.
- [x] **Stale busy slot deletion** — Fixed `_sync_source` in `sync_service.py`: `fetched_event_ids` is now collected from `all_items` in the same loop (not from `slots_to_upsert`), and events with `status == "cancelled"` are explicitly excluded from both `fetched_event_ids` and `slots_to_upsert` so cancelled slots in the DB are treated as stale and deleted.

> Tests: `backend/tests/test_email_normalization.py` (7 tests), `frontend/__tests__/sprint7/useNotifications.test.ts` (2 tests), `backend/tests/test_sync_service.py` (3 new stale-deletion tests, 13 total)

---

## Sprint 8 — Code Modularization

**Goal:** Audit the entire codebase for layering violations, oversized files, mixed responsibilities, and missing service abstractions. Produce a structured audit report (`docs/MODULARIZATION_AUDIT.md`), then refactor based on its findings.

> This is a reporting + refactor sprint. Part A produces the audit document only — no code changes. Parts B–D implement the fixes.

---

### Part A — Codebase audit (reporting only)

**Scope:**
- Backend: `routers/`, `services/`, `models/`, `utils/`, `scheduler/`
- Frontend: `hooks/`, `components/`, `app/`, `lib/`, `stores/`

**For each file, report:**
- Line count
- Stated vs. actual responsibility
- Layer violations (e.g. `HTTPException` in a service, `service_client` outside authorized files, direct Supabase calls in a router)
- Oversized files (>150 lines flagged)
- Duplication or logic that belongs in a different layer
- Missing service files (routers calling another service's table directly)

**Output:** `docs/MODULARIZATION_AUDIT.md` with:
- Per-file subsections organized by directory
- Summary table (file, lines, violations, severity: LOW / MEDIUM / HIGH / CRITICAL)
- Top-10 priority refactor list with justification

#### Done when
`docs/MODULARIZATION_AUDIT.md` exists and covers every file in the listed directories.

---

### Part B — Backend service layer cleanup

Based on audit findings:
- [ ] Extract `HTTPException` raises out of service files into router-level error translation
- [ ] Move unauthorized `service_client` usages to approved files or replace with `anon_client`
- [ ] Split oversized service files into focused modules
- [ ] Create missing service files for logic currently living in routers

#### Done when
No service file raises `HTTPException`. `service_client` only in authorized files. No service file exceeds 150 lines without clear justification.

---

### Part C — Frontend hook and component cleanup

Based on audit findings:
- [ ] Split oversized hook files
- [ ] Move inline API calls from components into hooks
- [ ] Consolidate duplicated fetch logic across hooks

#### Done when
No component calls `api.*` directly. No hook file mixes multiple unrelated domains.

---

### Part D — Dead code and import cleanup

- [ ] Remove all unused imports (backend + frontend)
- [ ] Remove dead utility functions and types
- [ ] Remove legacy columns from Pydantic models if already removed from schema

#### Done when
No unused imports. No dead functions. Codebase matches current schema.

---

## Sprint 9 — Polish, Performance & Real-time Completion

**Goal:** App feels fast. All real-time updates work. No rough edges.

> Complete parts in order.

---

### Part A — Real-time completion

- [ ] Wire remaining Supabase subscriptions: `busy_slots` changes → invalidate grid, participant joins → refresh participant list, `events.status` changes → all participants see confirmed state
- [ ] Presence indicator — show avatar dots of which participants are currently viewing the event page (use Supabase Presence channel)

#### Done when
All data on the event page updates live without refreshing. Presence dots show active viewers.

---

### Part B — UX & empty states

- [ ] Empty states: dashboard (no events yet), notifications (inbox empty), event page (no proposals yet, no preferred slots yet)
- [ ] Error boundaries on event page, dashboard, and settings — failed API calls show a toast notification instead of a blank screen
- [ ] 404 page for unknown event UIDs
- [ ] Loading skeletons for all async islands (participant list, proposals, grid)
- [ ] Timezone display — all times shown in user's local timezone via `lib/dates.ts`
- [ ] Mobile responsiveness pass on all pages
- [ ] Delete event from UI — coordinator only button on event page (currently only works via API)

#### Done when
No blank screens on error. Unknown event UIDs show a friendly 404. All times display in local timezone. App is usable on mobile.

---

### Part C — Performance & cleanup

- [ ] Audit event page SSR — consolidate all fetches into a single parallel `Promise.all`; page arrives fully populated
- [ ] Optimistic updates on preferred slot save — slot appears on grid immediately before API confirms
- [ ] Dashboard SSR — event list pre-rendered, no loading state on first paint
- [ ] Remove legacy columns from `profiles` (`google_auth_token`, `microsoft_auth_token`, `google_calendar_id`)
- [ ] Audit all `service_client` usages — confirm none where `anon_client` should be used instead
- [ ] Remove all dead code and unused imports

#### Done when
Page loads feel instant. No loading states on initial renders. Codebase has no legacy columns or dead code.