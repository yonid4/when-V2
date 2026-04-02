# Architecture — When. v2

## System overview

```
Browser
  │
  ├── Next.js (port 3000)
  │     ├── Server Components → fetch directly from FastAPI (port 8000)
  │     ├── Client Components → fetch via Next.js /api/* proxy routes
  │     └── Supabase JS client → real-time subscriptions only
  │
  └── FastAPI (port 8000)
        ├── Routes → Services → Supabase Python client
        ├── Google OAuth + Calendar API
        └── APScheduler (background calendar sync)

Supabase (PostgreSQL + real-time)
```

---

## Folder structure

### Backend

```
backend/
├── app/
│   ├── main.py                  # FastAPI app init, router registration, CORS, scheduler start
│   ├── config.py                # Settings via pydantic-settings (reads .env)
│   ├── dependencies.py          # get_current_user dependency, supabase client getters
│   │
│   ├── routers/                 # One file per feature domain
│   │   ├── auth.py              # /auth/google, /auth/google/callback, /auth/me
│   │   ├── events.py            # CRUD for events
│   │   ├── participants.py      # Participant management, RSVP
│   │   ├── invitations.py       # Invite by email, respond to invite
│   │   ├── calendar_accounts.py # Connect/disconnect Google Calendar accounts
│   │   ├── calendar_sources.py  # Toggle calendar sources, set write calendar
│   │   ├── busy_slots.py        # Get merged busy slots, manual sync trigger
│   │   ├── preferred_slots.py   # Save/get/delete preferred slots
│   │   ├── proposals.py         # Get proposals, force refresh
│   │   ├── finalization.py      # Finalize event, create Google Calendar event
│   │   └── notifications.py     # Get notifications, mark read, take action
│   │
│   ├── services/                # Business logic, no HTTP concerns
│   │   ├── auth_service.py      # OAuth token exchange, JWT creation, profile upsert
│   │   ├── event_service.py     # Event CRUD, UID generation
│   │   ├── participant_service.py
│   │   ├── invitation_service.py # Invite logic, pending invite matching on signup
│   │   ├── calendar_service.py  # Google Calendar API calls (read + write)
│   │   ├── sync_service.py      # Fetch busy times, upsert busy_slots
│   │   ├── proposal_service.py  # Scheduling algorithm (see algorithm section)
│   │   └── notification_service.py
│   │
│   ├── models/                  # Pydantic request/response models
│   │   ├── event.py
│   │   ├── participant.py
│   │   ├── invitation.py
│   │   ├── calendar.py
│   │   ├── slot.py              # BusySlot, PreferredSlot, ProposedTime
│   │   └── notification.py
│   │
│   ├── scheduler/
│   │   └── jobs.py              # APScheduler job definitions (calendar auto-sync)
│   │
│   └── utils/
│       ├── supabase.py          # anon_client and service_client singletons
│       ├── dates.py             # UTC conversion helpers
│       └── uid.py               # 12-char UID generator
│
├── tests/                       # pytest test suite (one file per feature domain)
│   ├── __init__.py
│   ├── test_auth.py             # Sprint 1: auth router, service, get_current_user dependency
│   └── test_events.py          # Sprint 2: event service CRUD, access control
│
├── .env                         # Never committed
├── .env.example
└── requirements.txt
```

### Frontend

```
frontend/
├── app/                         # Next.js App Router
│   ├── layout.tsx               # Root layout: providers (QueryClient, Zustand, Supabase)
│   ├── page.tsx                 # Landing / login page (server component)
│   ├── auth/
│   │   └── callback/
│   │       └── page.tsx         # Handles OAuth redirect, stores JWT, redirects to dashboard
│   ├── dashboard/
│   │   └── page.tsx             # Server component: fetches event list, renders EventCard list
│   ├── events/
│   │   ├── new/
│   │   │   └── page.tsx         # Create event wizard (client component)
│   │   └── [uid]/
│   │       └── page.tsx         # Event detail (server component shell + client islands)
│   └── settings/
│       └── page.tsx             # Calendar accounts, timezone
│
├── api/                         # Next.js API proxy routes (client → FastAPI)
│   └── [...path]/
│       └── route.ts             # Catch-all proxy: forwards requests to FastAPI with JWT
│
├── components/
│   ├── ui/                      # shadcn/ui generated components (do not edit manually)
│   ├── auth/
│   │   └── LoginButton.tsx
│   ├── dashboard/
│   │   └── EventCard.tsx
│   ├── event/
│   │   ├── EventHeader.tsx      # Name, status badge, coordinator controls
│   │   ├── ParticipantList.tsx
│   │   ├── AvailabilityGrid.tsx # The calendar grid (busy/preferred/proposed overlays)
│   │   ├── ProposalPanel.tsx    # List of proposed times with reasoning
│   │   ├── FinalizeButton.tsx
│   │   └── InviteInput.tsx
│   ├── notifications/
│   │   ├── NotificationBell.tsx # Badge + dropdown trigger
│   │   └── NotificationList.tsx
│   └── settings/
│       ├── CalendarAccountCard.tsx
│       └── CalendarSourceList.tsx
│
├── hooks/                       # TanStack Query hooks (one file per domain)
│   ├── useEvent.ts              # useEvent(uid), useEvents(), useUpdateEvent()
│   ├── useParticipants.ts
│   ├── useInvitations.ts
│   ├── useBusySlots.ts
│   ├── usePreferredSlots.ts
│   ├── useProposals.ts
│   ├── useNotifications.ts
│   ├── useCalendarAccounts.ts
│   └── useFinalize.ts
│
├── stores/                      # Zustand stores
│   ├── authStore.ts             # { user, token, setUser, clearAuth }
│   └── notificationStore.ts     # { unreadCount, increment, reset }
│
├── lib/
│   ├── api.ts                   # Base fetch wrapper (attaches JWT, handles 401)
│   ├── dates.ts                 # UTC ↔ local timezone conversion utilities
│   ├── supabase.ts              # Supabase JS client singleton (real-time only)
│   └── uid.ts                   # URL helpers
│
├── types/
│   └── index.ts                 # All TypeScript interfaces (Event, Participant, etc.)
│
└── middleware.ts                # Next.js middleware: redirect to / if no JWT
│
└── __tests__/                   # Vitest test suite
    ├── setup.ts                 # @testing-library/jest-dom/vitest global setup
    ├── auth/
    │   ├── authStore.test.ts    # Sprint 1: Zustand authStore state and localStorage
    │   ├── middleware.test.ts   # Sprint 1: Next.js middleware redirect logic
    │   ├── CallbackPage.test.tsx # Sprint 1: /auth/callback token storage + redirect
    │   └── api.test.ts          # Sprint 1: lib/api Authorization header + 401 handling
    ├── EventCard.test.tsx       # Sprint 2: EventCard rendering
    └── CreateEventForm.test.tsx # Sprint 2: multi-step create event form
```

---

## Data flow patterns

### Server component page load (fast, no skeleton)

```
User navigates to /events/[uid]
  → Next.js server component runs on server
  → Calls FastAPI directly: GET http://localhost:8000/events/{uid}
  → Calls FastAPI directly: GET http://localhost:8000/events/{uid}/busy-slots
  → Calls FastAPI directly: GET http://localhost:8000/events/{uid}/proposals
  → All data arrives before HTML is sent to browser
  → Page renders fully populated, zero loading states
  → Client components hydrate and attach real-time subscriptions
```

### Client mutation flow (optimistic where possible)

```
User drags to mark a preferred slot
  → useMutation fires POST /api/preferred-slots/{uid}
  → Optimistic update: immediately add slot to local TanStack Query cache
  → Grid renders instantly with new slot (no spinner)
  → On success: server confirms, set proposals_needs_regeneration = true
  → invalidateQueries(['proposals', uid]) → proposals refetch in background
  → On error: roll back optimistic update, show toast
```

### Real-time update flow

```
Another participant saves a preferred slot
  → Supabase real-time fires on preferred_slots INSERT
  → Client receives event
  → queryClient.invalidateQueries(['preferredSlots', uid])
  → Grid refetches and updates
```

### Notification flow

```
Event is finalized
  → FastAPI notification_service creates notification rows for all participants
  → Supabase real-time fires on notifications INSERT for each user
  → Each user's client: notificationStore.increment()
  → Bell badge updates instantly
  → User opens inbox: useNotifications() query refetches
```

---

## Authentication flow

```
1. User clicks "Sign in with Google"
2. Frontend redirects to GET /auth/google
3. FastAPI redirects to Google OAuth consent screen
4. Google redirects to GET /auth/google/callback?code=...
5. FastAPI exchanges code for tokens
6. FastAPI upserts profile in Supabase (using service_client)
7. FastAPI checks event_invitations for pending invites matching email → creates notifications
8. FastAPI creates JWT containing { user_id, email }
9. FastAPI redirects to /auth/callback?token=...
10. Next.js /auth/callback page stores token in localStorage
11. authStore.setUser() called with decoded user
12. Redirect to /dashboard
```

---

## API design rules

- All routes prefixed with `/api` (e.g. `GET /api/events`)
- All request bodies validated by Pydantic models — never access `request.json()` directly
- All responses return Pydantic models — never return raw dicts
- Auth: every protected route has `current_user: User = Depends(get_current_user)`
- Errors: use FastAPI's `HTTPException` with appropriate status codes
  - 400 — bad input
  - 401 — not authenticated
  - 403 — authenticated but not authorized (e.g. non-coordinator trying to finalize)
  - 404 — resource not found
  - 409 — conflict (e.g. duplicate invite)
- Coordinator-only actions check `event.coordinator_id == current_user.id` in the service layer

---

## Scheduling algorithm (proposal_service.py)

Replaces Gemini AI. Fully deterministic and testable.

```
Input:
  - event: { earliest_datetime_utc, latest_datetime_utc, duration_minutes }
  - busy_slots: list of { user_id, start_time_utc, end_time_utc }
  - preferred_slots: list of { user_id, start_time_utc, end_time_utc }
  - participants: list of { user_id }

Step 1 — Generate candidate windows
  Slide a window of `duration_minutes` across the event range in 30-min increments
  → produces N candidate (start, end) pairs

Step 2 — Score each candidate
  conflict_count = number of participants with a busy_slot overlapping this window
  preferred_count = number of participants with a preferred_slot overlapping this window

Step 3 — Build reasoning string
  "{preferred_count}/{total} participants marked this time as preferred,
   {conflict_count}/{total} have a conflict"

Step 4 — Rank
  Sort by: conflict_count ASC, then preferred_count DESC
  Take top 5

Step 5 — Store
  Delete existing proposed_times for this event
  Insert top 5 with rank 1–5, conflict count, reasoning

Output: 5 ProposedTime objects
```

---

## Supabase usage rules

- **anon_client** — used for all user-facing queries. RLS policies enforce that users can only read/write their own data.
- **service_client** — used ONLY in:
  - `auth_service.py` (profile upsert on login)
  - `invitation_service.py` (pending invite matching on new user signup)
  - `notification_service.py` (inserting notifications for other users)
  - `scheduler/jobs.py` (background sync across all users)
- Never use service_client in a route directly — only call it from a service function
- All other service functions receive the current user's ID and use anon_client with RLS

---

## Environment variables

```env
# Backend (.env in /backend)
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
JWT_SECRET_KEY=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080   # 7 days

# Frontend (.env.local in /frontend)
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
API_URL=http://localhost:8000   # server-side only (no NEXT_PUBLIC)
```
