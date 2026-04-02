# CLAUDE.md — When. v2

This file tells Claude Code how to work in this repository. Read it fully before writing any code.

---

## Project overview

When. is a group event coordination app. Users create events with a time window, invite participants, sync their Google Calendars to share availability, and a deterministic algorithm proposes the best meeting times. Coordinators finalize a time which creates a real Google Calendar event.

**Stack:** FastAPI (Python) + Next.js 14 (TypeScript) + Supabase (PostgreSQL + real-time) + shadcn/ui + TanStack Query + Zustand

---

## Repo structure

```
when-v2/
├── backend/         # FastAPI app
├── frontend/        # Next.js app
├── docs/
│   ├── CLAUDE.md
│   ├── ARCHITECTURE.md
│   ├── DATA_MODEL.md
│   ├── SPRINT_PLAN.md
│   └── TECH_STACK.md
└── README.md
```

---

## Dev commands

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate   # first time only
pip install -r requirements.txt                    # first time only
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install          # first time only
npm run dev          # runs on port 3000
```

### Both together
Run backend in one terminal, frontend in another. No Docker.

### Tests
```bash
# Backend
cd backend && source venv/bin/activate
pytest tests/ -v

# Frontend
cd frontend
npx vitest run
```

---

## Testing rules

- Backend tests live in `backend/tests/` — one file per feature domain matching the router/service it covers
- Frontend tests live in `frontend/__tests__/` — one directory per feature domain
- Mock Supabase clients (`service_client`, `anon_client`) in every backend test — never hit a real database
- Mock `next/navigation` (`useRouter`, `useSearchParams`) in every component test that uses them
- Mock `lib/api` in component tests; test `lib/api` itself directly in `api.test.ts`
- Use `useAuthStore.setState(...)` to reset Zustand between tests — re-importing does not reset store state
- Always read `docs/LESSONS_LEARNED.md` before writing new tests — implementation details frequently differ from the design docs

---

## Backend rules

### Structure
- One router file per feature domain in `app/routers/`
- One service file per feature domain in `app/services/`
- Business logic lives in services only — routers call services, never touch Supabase directly
- Pydantic models in `app/models/` — one file per domain

### Always
- Use `current_user: User = Depends(get_current_user)` on every protected route
- Validate all request bodies with Pydantic models — never use `request.json()` directly
- Return Pydantic response models — never return raw dicts
- Use `HTTPException` with correct status codes (400/401/403/404/409)
- Check coordinator authorization in the service layer: `if event.coordinator_id != user.id: raise HTTPException(403)`

### Never
- Never put business logic in router files
- Never use `service_client` (bypasses RLS) in a router — only in service functions
- Never store credentials or secrets in code — always read from `app/config.py`
- Never call Google Calendar API from a router directly — always through `calendar_service.py`

### Supabase client usage
- `anon_client` — default for all user queries (respects RLS)
- `service_client` — ONLY in: auth_service.py, invitation_service.py, notification_service.py, scheduler/jobs.py

### Error handling
```python
# Correct pattern
result = supabase.table("events").select("*").eq("uid", uid).single().execute()
if not result.data:
    raise HTTPException(status_code=404, detail="Event not found")
```

---

## Frontend rules

### Structure
- Pages in `app/` — server components by default
- Client components must have `"use client"` at top
- All API calls go through hooks in `hooks/` — never call fetch directly from a component
- One hook file per domain: useEvent.ts, useParticipants.ts, etc.
- shadcn/ui components go in `components/ui/` (auto-generated — do not edit manually)
- Custom components go in `components/{domain}/`

### Data fetching pattern
```typescript
// Server component (SSR — fast, no loading state)
// app/events/[uid]/page.tsx
const event = await fetch(`${process.env.API_URL}/api/events/${uid}`, {
  headers: { Authorization: `Bearer ${getServerToken()}` }
}).then(r => r.json())

// Client component (TanStack Query — real-time, mutations)
// components/event/ProposalPanel.tsx
const { data: proposals } = useProposals(uid)
const { mutate: refreshProposals } = useRefreshProposals(uid)
```

### TanStack Query conventions
- Query keys must be arrays: `['event', uid]`, `['events']`, `['proposals', uid]`
- After any mutation that changes data, invalidate affected queries:
  ```typescript
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['proposals', uid] })
  }
  ```
- Use optimistic updates for preferred slot saves (immediate grid feedback)

### Zustand usage
- `authStore`: `{ user, token, setUser, clearAuth }` — current logged-in user globally
- `notificationStore`: `{ unreadCount, increment, reset }` — drives the bell badge
- Do not put server data in Zustand — that belongs in TanStack Query

### API calls from client components
All client-side fetches go through the Next.js proxy (`/api/*`), never directly to `localhost:8000`.

```typescript
// lib/api.ts — always use this, never raw fetch
import { api } from '@/lib/api'
const event = await api.get(`/events/${uid}`)
```

### Dates
- Never use `new Date()` directly in display code
- Always use helpers from `lib/dates.ts` for timezone-aware display
- All times stored UTC, displayed in user's local timezone

### TypeScript
- No `any` types — ever
- All API response shapes must have a TypeScript interface in `types/index.ts`
- Interfaces should mirror the Pydantic response models from the backend

---

## Scheduling algorithm

The proposal algorithm lives in `backend/app/services/proposal_service.py`. It is deterministic — no AI, no external API calls.

Logic:
1. Generate candidate windows (30-min sliding window over event range)
2. Score each by: conflict_count (participants with overlapping busy_slots) and preferred_count (participants with overlapping preferred_slots)
3. Build reasoning string: "X/Y participants free, Z marked this time as preferred"
4. Rank: conflicts ASC, preferred_count DESC — take top 5
5. Delete old proposed_times for event, insert new ones

Trigger: called when `proposals_needs_regeneration = true` or force-refresh requested.
Any write to `busy_slots` or `preferred_slots` must set `proposals_needs_regeneration = true` on the event.

---

## Real-time conventions

Supabase real-time subscriptions live in `lib/supabase.ts` (the JS client). They are set up in client components using `useEffect`.

Pattern for each subscription:
```typescript
useEffect(() => {
  const channel = supabase
    .channel(`preferred-slots-${eventId}`)
    .on('postgres_changes',
      { event: 'INSERT', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${eventId}` },
      () => queryClient.invalidateQueries({ queryKey: ['preferredSlots', eventId] })
    )
    .subscribe()
  return () => supabase.removeChannel(channel)
}, [eventId])
```

Active subscriptions:
- `notifications INSERT` → notificationStore.increment() + invalidate notifications query
- `preferred_slots INSERT/DELETE` (per event) → invalidate preferredSlots + proposals queries
- `busy_slots INSERT` (per event participants) → invalidate busySlots query
- `event_participants INSERT` → invalidate participants query
- `events UPDATE` (per event) → invalidate event query (catches status → confirmed)

---

## What not to do

- Do not use Gemini or any AI API for proposals — use the deterministic algorithm only
- Do not add Microsoft OAuth, Microsoft Graph API, or Teams integration — deferred to a future version
- Do not use Docker — local dev only for now
- Do not use SQLAlchemy or any ORM — use the Supabase Python client directly
- Do not put secrets in frontend code — only `NEXT_PUBLIC_*` vars are safe to expose
- Do not bypass RLS by using service_client in a route handler
- Do not write CSS files — use Tailwind utility classes only
- Do not edit files in `components/ui/` — these are shadcn generated components
- Do not use `any` in TypeScript

---

## Reference docs

- Full architecture and folder structure: `docs/ARCHITECTURE.md`
- Database schema with column details: `docs/DATA_MODEL.md`
- All technology choices with reasoning: `docs/TECH_STACK.md`
- Sprint breakdown with task checklists: `docs/SPRINT_PLAN.md`


## Design reference

The `design/` folder contains Stitch-generated HTML files that are the 
visual source of truth for every page. Before building any component or page:

1. Read `design/DESIGN.md` for the full design system rules
2. Open the relevant HTML file for the page you are building
3. Replicate the visual design exactly using shadcn/ui components + Tailwind
4. Replace Stitch's raw HTML elements with shadcn primitives (Button, Card, Badge, etc.)
5. Replace Material Symbols icons with lucide-react equivalents
6. Replace hardcoded Tailwind colors with the CSS variables defined in globals.css

Never copy Stitch HTML directly into the Next.js codebase.
Always rebuild using shadcn components that match the visual output.