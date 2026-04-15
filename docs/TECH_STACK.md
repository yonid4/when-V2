# Tech Stack — When. v2

## Decision summary

Every tool below was chosen over alternatives. Reasoning is included so future decisions stay consistent with the same principles.

---

## Backend

### Runtime & framework
**FastAPI** (Python)

Chosen over Flask (v1 stack) because FastAPI gives automatic OpenAPI docs, native async support, and Pydantic validation built in. Every route automatically validates request bodies and serializes responses — no manual validation layer needed. The type hints also make Claude Code generate more accurate code since the schema is explicit.

### Data validation
**Pydantic v2**

Comes bundled with FastAPI. Used for all request/response models. Define a model once, get validation, serialization, and OpenAPI schema for free.

### Authentication
**python-jose + passlib** for JWT encoding/decoding
**Google OAuth 2.0** via `google-auth` library

JWT tokens stored in `localStorage` on the frontend (acceptable for local dev, upgrade to httpOnly cookies before production). All protected routes use a `get_current_user` FastAPI dependency.

### Calendar integration
**google-api-python-client** for Google Calendar API reads and writes
**google-auth-oauthlib** for the OAuth flow

### Background jobs
**APScheduler** (in-process scheduler)

Chosen over Celery (too heavy for this scale) and Supabase Edge Functions (adds deployment complexity). APScheduler runs inside the FastAPI process and handles periodic calendar syncs per user.

### Database client
**supabase-py** (official Python client)

Two clients initialized at startup:
- `anon_client` — uses the anon key, respects RLS policies
- `service_client` — uses the service role key, bypasses RLS (used only for admin operations like the profile creation hook)

### Dev server
**Uvicorn** with `--reload` flag for local development

---

## Frontend

### Framework
**Next.js 14** (App Router)

Chosen over plain React (v1 stack) for:
- Server Components — fetch data on the server, ship pre-populated HTML, no skeleton flash on first load
- App Router file-based routing — cleaner than React Router
- Built-in API routes — used as a proxy layer so client components don't call FastAPI directly

### Language
**TypeScript**

Mandatory. Catches entire classes of bugs before runtime, and Claude Code generates significantly better code when types are explicit. All API response shapes typed with interfaces matching the Pydantic models on the backend.

### UI components
**shadcn/ui**

Chosen over Chakra UI (v1 stack) because shadcn components are copy-pasted into your repo (you own the code, not a node_modules black box), Tailwind-based (consistent with the rest of the styling), and highly composable. Easy to customize without fighting the library.

Underlying headless primitive layer: **`@base-ui/react`** (replaces Radix UI in shadcn v4+). Components like `Button` and `DropdownMenu` import from `@base-ui/react/*` rather than `@radix-ui/*`.

### Styling
**Tailwind CSS v4**

Utility-first. No separate CSS files. Works seamlessly with shadcn/ui. v4 uses a CSS-first configuration (`@import "tailwindcss"` in globals.css) instead of `tailwind.config.js`.

### Server state (data fetching + caching)
**TanStack Query (React Query) v5**

Handles all server state: fetching, caching, background refetching, and invalidation after mutations. Used for all API calls from client components.

Key patterns used in this app:
- `useQuery` for reads (event detail, participants, proposals, notifications)
- `useMutation` + `queryClient.invalidateQueries` for writes (save preferred slot → invalidate proposals, finalize event → invalidate event detail)
- Parallel queries on the event page to load all data simultaneously

### Client state (global UI state)
**Zustand v5**

Used only for state that is not server data:
- Current authenticated user object (available globally without prop drilling)
- Notification unread count (updated via Supabase real-time, read by the bell icon anywhere)
- Any transient UI state that needs to cross component boundaries

Kept minimal — if it lives in the database, it belongs in TanStack Query, not Zustand.

### Real-time
**Supabase JS client** (`@supabase/supabase-js`)

Supabase real-time subscriptions for:
- New notifications → update Zustand notification count + inbox
- Preferred slots changes → invalidate TanStack Query cache for the availability grid
- Event status changes → invalidate event detail query
- Participant joins → invalidate participant list query

### Forms
**React Hook Form + Zod**

React Hook Form for form state and submission. Zod for schema validation (shares shape with Pydantic models on the backend). Used for: create event form, invite by email, settings.

### Date handling
**date-fns + date-fns-tz**

Same as v1. All times stored as UTC in the database, converted to the user's local timezone for display using `date-fns-tz`. Never use `new Date()` directly — always go through the utility functions in `lib/dates.ts`.

### Testing
**Vitest** as the test runner (replaces Jest)
**@testing-library/react** for component rendering and querying
**@testing-library/jest-dom** for DOM matchers (`toBeInTheDocument`, etc.)
**jsdom** as the simulated browser environment

Vitest was chosen over Jest because it uses the same Vite pipeline already configured for the frontend — no separate Babel transform or tsconfig needed. Tests run with `npm run test` (`vitest run`).

Component tests mock `next/navigation` hooks and `lib/api` — they never make real network calls.

---

## Backend testing
**pytest** with `unittest.mock` (standard library)
**FastAPI TestClient** (from `starlette.testclient`) for route-level integration tests

No extra test libraries needed. All Supabase calls are patched via `@patch` so tests run without a live Supabase instance. Tests live in `backend/tests/`, one file per feature domain.

---

## Database & infrastructure

### Database
**Supabase (PostgreSQL)**

Kept from v1. Provides the database, auth (used only for user identity — JWT issued by our own FastAPI backend), real-time subscriptions, and Row Level Security.

### Local development
Plain `uvicorn` + `npm run dev`. No Docker for now. Add Docker Compose before any deployment.

---

## Explicitly NOT used (and why)

| Tool | Why skipped |
|---|---|
| Microsoft OAuth / Graph API | Deferred to a future sprint |
| Gemini AI | Replaced by deterministic scheduling algorithm |
| Celery | Too heavy — APScheduler sufficient for this scale |
| tRPC | Adds complexity; typed fetch functions + Pydantic models cover the type-safety need |
| Prisma / SQLAlchemy | Supabase client handles all queries; no ORM needed |
| Docker (for now) | Local dev only; add before first deployment |
