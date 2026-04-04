# Lessons Learned

Implementation details discovered while writing tests that aren't captured elsewhere in the docs.

---

## Sprint 1 — Auth

### Backend

- **`RedirectResponse` returns 307 by default, not 302.**
  FastAPI's `RedirectResponse` defaults to HTTP 307 (Temporary Redirect). Tests asserting a redirect from `/auth/google` must accept `307` (or explicitly check for `in (302, 307)`). The router does not pass `status_code=302`, so 307 is the real behavior.

- **`HTTPBearer` returns 403 (not 401) when the Authorization header is absent.**
  FastAPI's built-in `HTTPBearer` dependency returns a `403 Forbidden` when no `Authorization` header is sent at all. It only reaches the JWT decode logic (and can return 401) when a malformed/expired token is supplied. Tests for "missing token" must assert 403; tests for "invalid token" assert 401.

- **`get_current_user` returns 401 (not 404) for an unknown user.**
  When a valid JWT is decoded but the `user_id` is not found in `profiles`, the dependency raises `HTTP 401` ("User not found"). The spec listed "401 or 404" as acceptable — the implementation chose 401. Tests should assert 401.

- **JWT claims use `sub` for `user_id`, not `user_id` directly.**
  The JWT payload stores the user ID under the key `"sub"` (standard JWT subject claim) and the email under `"email"`. The `get_current_user` dependency reads `payload.get("sub")` for the user ID.

- **`_process_pending_invitations` sets `invitee_id`, creates an `event_invitation` notification for the new user, and does not change invitation status or create a participant row.**
  When a new user signs up and their email matches a pending invitation, the backend: (1) sets `invitee_id` on the invitation row to the new user's id, (2) creates an `event_invitation` notification for the new user so they can accept or decline, (3) leaves `status` as `pending`. The user is only added to `event_participants` when they explicitly accept via `PUT /api/invitations/{id}/respond`.

- **`_upsert_profile` does NOT write `google_auth_token` to the profiles row.**
  The v2 implementation correctly stores OAuth credentials only in `calendar_accounts.credentials`. The profiles upsert dict contains only: `id`, `email_address`, `full_name`, `avatar_url`, `updated_at`. The legacy `google_auth_token` column is never touched.

### Frontend

- **`npm run test` script was missing from `package.json`.**
  `vitest` was listed as a dev dependency but no `"test"` script was defined in `package.json`. Added `"test": "vitest run"` and `"test:watch": "vitest"`.

- **`useAuthStore` uses Zustand's `setState` for test resets, not re-import.**
  Between tests, the store can be reset with `useAuthStore.setState({ user: null, token: null })`. Re-importing the module does not reset Zustand state in the same test process.

- **`lib/api.ts` is marked `'use client'` — dynamic import is needed in tests.**
  Because `lib/api.ts` has a `'use client'` directive and reads from `localStorage`, the module is safe to import in jsdom but its internal `getToken()` reads `localStorage` at call time (not module-load time). Each test that wants a fresh token state must set `localStorage` before calling `api.*`, not before importing the module.

- **The middleware does NOT redirect `/` → `/dashboard` when a token exists.**
  `/` is in `PUBLIC_PATHS`, so the middleware always passes it through regardless of token. The redirect from `/` to `/dashboard` for logged-in users (if desired) is the responsibility of the page component, not the middleware. The middleware's only job is to protect non-public paths.

- **`next/navigation` must be fully mocked in component tests.**
  `useRouter`, `useSearchParams` are Next.js hooks that throw in a non-Next.js test environment. Both must be mocked via `vi.mock('next/navigation', ...)` before rendering any component that calls them.

---

## Sprint 3 — Participants, Invitations, Notifications

### Backend

- **Flat MagicMock chains break when a service queries two different tables with the same chain depth.**
  The Supabase Python client's fluent interface produces structurally identical chains regardless of which table is queried. When a service function queries both `events` and `event_participants` via the same `db` mock (e.g. `db.table('events').select(...).eq(...).maybe_single().execute()` and `db.table('event_participants').select(...).eq(...).maybe_single().execute()`), setting `db.table.return_value.select.return_value...` will make both queries return the same value — whichever was set last wins. Fix: route per table name using `db.table.side_effect = lambda name: table_mock_dict[name]`.

- **`invitation_service.invite_by_email` checks coordinator status BEFORE the participant row check.**
  The original implementation required a participant row to exist for ALL callers, including the coordinator. This caused an incorrect 403 for coordinators who are not also listed in `event_participants`. The fix: check `is_coordinator = event['coordinator_id'] == current_user.id` first, and only query `event_participants` if the user is NOT the coordinator.

- **`get_event_by_uid` uses `.maybe_single()` not `.single()`.**
  `.single()` raises a Supabase exception if 0 rows are returned; `.maybe_single()` returns `None` gracefully. The service was updated to use `.maybe_single()`. All `test_events.py` mocks that used `.single.return_value` must be updated to `.maybe_single.return_value`. Also add `"maybe_single"` to the list of chained methods in `_make_chain()` helpers.

- **`notification_service.take_action` internally calls `invitation_service.respond_to_invitation`, which calls `get_authed_client` separately.**
  Both services receive a patched `get_authed_client`. When both patches point to the same `db` mock AND `respond_to_invitation` queries `events` with the same chain depth as the prior `notifications` query, the later mock assignment overwrites the earlier one. Fix: use per-table routing on the shared `db` mock in the `test_take_action_accept` test.

- **`_make_invitation_row` default `invitee_id` must match the current user in respond tests.**
  `respond_to_invitation` checks `invite.get('invitee_id') != current_user.id` and raises 403 on mismatch. The respond tests use `_auth_headers()` which sets `user_id = "user-uuid-1"`, so `invitee_id` in the default invitation row must also be `"user-uuid-1"`.

### Frontend

- **`vi.mock` factory closures cannot reference outer `const` variables — use `vi.hoisted` or inline `vi.fn()` calls.**
  Vitest hoists `vi.mock(...)` calls to the top of the file, before `const` declarations are initialized. If a `vi.mock` factory references variables like `const mockFn = vi.fn()` declared at module level, you get `ReferenceError: Cannot access 'mockFn' before initialization`. Fix: either inline `vi.fn()` directly in the factory, or use `vi.hoisted(() => ({ ... }))` to declare shared mock refs.

- **`<input type="email">` in JSDOM blocks form submission for invalid addresses.**
  JSDOM's email input validation silently prevents the browser's form `submit` event from firing when the value fails the built-in email format check. This means the React `onSubmit` handler never runs, and any custom regex validation inside it is never reached — the test expecting a custom error message will fail. Fix: use `type="text"` and rely entirely on the JavaScript regex validation.

- **`@/components/ui/popover` is not auto-installed — it must be created manually.**
  shadcn/ui components like `Popover` are not included in the base install; they need to be generated via `npx shadcn-ui@latest add popover` or written manually. If missing, Vite throws `Failed to resolve import` at transform time, preventing any test in any file that imports the component from running. A minimal hand-rolled implementation (using native React state) is sufficient when no Radix UI dependency is available.

---

## Sprint 4 — Calendar Integration & Busy Slot Sync

### Backend

- **The Write tool requires reading a file before overwriting it — even 1-line stubs.**
  All three router stubs (`calendar_accounts.py`, `calendar_sources.py`, `busy_slots.py`) existed as placeholder files. The Write tool refuses to overwrite a file that hasn't been read in the current session with "File has not been read yet." Always read first even when you know the file is a stub.

- **`busy_slots.user_id` references `auth.users(id)`, not `profiles(id)` — `service_client` is required for all writes.**
  `busy_slots` rows are keyed to `auth.users` directly. RLS policies on that table prevent the `anon_client` (user-scoped) from inserting rows. All upserts to `busy_slots` must use `service_client`. Similarly, `calendar_accounts.credentials` stores raw OAuth tokens — never expose these via the `anon_client` path.

- **Google Calendar OAuth uses a `state` parameter to carry `user_id` through the callback.**
  The `/calendar-accounts/connect` endpoint stores `user_id` in the `state` query parameter sent to Google. The `/calendar-accounts/callback` endpoint reads it back from `state` (not from a session or cookie) to associate the returned credentials with the correct user. This is necessary because the callback runs without an authenticated request context.

- **APScheduler must be started inside FastAPI's `lifespan` asynccontextmanager, not `@app.on_event`.**
  `@app.on_event("startup")` is deprecated in FastAPI. The correct pattern is an `@asynccontextmanager` passed to `FastAPI(lifespan=...)`. The scheduler is created and started in the `lifespan` function before the `yield`, and shut down after. The `BackgroundScheduler` from `apscheduler.schedulers.background` works fine in a sync context inside the async lifespan.

- **`is_write_calendar=True` must be exclusive per user — use a Supabase RPC to clear others atomically.**
  When a user sets a calendar source as their write calendar, all other sources belonging to that user must be cleared atomically. This requires a Postgres function (`clear_write_calendar_for_user(p_user_id, p_exclude_source_id)`) invoked via `service_client.rpc(...)`. A Python-level loop of UPDATE queries is not atomic and risks partial state.

- **`sync_event_participants` should include `status='invited'` participants, not only `'accepted'`.**
  Invited participants who haven't responded yet may still need their busy slots synced so the coordinator can see provisional availability. The status filter uses `.in_("status", ["accepted", "invited"])`.

- **Mocking `app.routers.busy_slots.service_client` for router-level tests.**
  The `busy_slots` router calls `service_client` directly (to check coordinator authorization without going through a service). Router tests must patch both `app.routers.busy_slots.service_client` (for the coordinator check) and `app.services.sync_service.service_client` (for the actual sync). Patching only the service module leaves the router-level call unmocked and causes real DB hits.

### Frontend

- **`screen.getByText('Settings')` fails when both a nav link and an `<h1>` contain the same text.**
  Two elements matched `getByText('Settings')`: the nav link and the page heading. The fix is `screen.getByRole('heading', { level: 1, name: 'Settings' })` which uniquely identifies the `<h1>`.

- **Running `npx vitest run` from the repo root finds no test files.**
  Vitest is configured relative to `frontend/`. Running it from the project root (without `cd frontend`) produces "No test files found". Always `cd frontend` first or use `cd frontend && npx vitest run`.

- **The `venv/bin/pytest` path is the correct invocation for backend tests in this project.**
  `python -m pytest` and `python3 -m pytest` both failed with import errors because the system Python isn't the venv Python. The correct command is `backend/venv/bin/pytest tests/ -v` (or `source venv/bin/activate` first).

---

## Sprint 4 (Post) — Auth, Calendar & UI Rework

- **`NotificationList` calls `useRouter()` — all tests that render it must mock `next/navigation`.**
  After adding `useRouter()` to `NotificationList` for the calendar-required redirect, every test that renders the component crashed with "invariant expected app router to be mounted". Fix: add `vi.mock('next/navigation', () => ({ useRouter: () => ({ push: vi.fn(), replace: vi.fn() }) }))` to any test file that renders `NotificationList`.

- **Middleware that redirects `/` to `/dashboard` for authenticated users must be reflected in tests.**
  The middleware test for "passes through `/` with a valid token" became "redirects to `/dashboard` with a valid token" (status 307, location `/dashboard`). Any time middleware behavior changes for public paths, audit `middleware.test.ts` immediately.

- **Calendar connect via `<a href>` strips the Authorization header — use a fetch-then-redirect pattern.**
  Browser anchor navigation does not send the `Authorization: Bearer` header. The fix: add a `GET /api/calendar-accounts/connect-url` endpoint that returns `{ url }` as JSON, then redirect from the frontend using `window.location.href = url` after fetching with `api.get(...)`. The original `/connect` endpoint is kept but unused by the frontend.

- **Login flow must request identity scopes only — calendar scopes belong to the explicit connect flow.**
  Including `calendar.readonly` and `calendar.events` in the login OAuth flow causes users to see calendar permission requests at sign-in. Auth scopes must be `openid`, `email`, `profile` only. Calendar credentials are obtained separately during the explicit calendar connect flow and stored in `calendar_accounts`.

- **`_upsert_calendar_account` must not be called from the login callback.**
  The login callback only upserts the profile row, processes pending invitations, and issues the JWT. The `calendar_accounts` row is created only when the user explicitly connects a calendar via the connect flow. Calling it at login created orphaned `calendar_accounts` rows with no `calendar_sources`, causing silent sync failures.

- **`<NotificationBell />` must be mounted via a shared `Navbar` component, not per-page.**
  Mounting the bell only on the settings page left the dashboard and event pages with a dead static icon or no bell at all. Fix: create `components/layout/Navbar.tsx` and import it in each authenticated page (dashboard, settings, event detail). Do not add it to the root layout — landing and auth pages must not show the navbar.

- **Users must have at least one `calendar_sources` row before accepting an event invitation.**
  `invitation_service.respond_to_invitation` now checks for a connected calendar before accepting. If none exists it raises `HTTPException(422, detail="calendar_required")`. The frontend catches this specific detail string and redirects to `/settings?connect_calendar=true`.

- **`GOOGLE_CALENDAR_REDIRECT_URI` must be explicitly set in `.env` — do not rely on the hardcoded default.**
  The `Settings` class has a default of `http://localhost:8000/api/calendar-accounts/callback` but this must be present in `.env` explicitly. Missing it caused silent token exchange failures when the Google Cloud Console registered URI differed from the default in any way.

- **Wrap all DB calls in the calendar callback with try/except and `exc_info=True`.**
  The `/calendar-accounts/callback` endpoint had no try/except around `connect_google_account`. Any DB error (FK violation, RLS, schema mismatch) bubbled up as an unhandled 500 with no user-facing redirect and no traceback in logs. All service calls in OAuth callbacks must be wrapped with `logger.error(..., exc_info=True)` and redirect to an error page on failure.

- **`flow.oauth2session.scope = None` suppresses scope validation and should be removed.**
  This hack was added to suppress google-auth's scope mismatch check during the calendar OAuth callback. Removing it and passing scopes explicitly to `Flow.from_client_config` is the correct fix. The hack can cause subtle failures depending on the `requests-oauthlib` version.

- **The `AvailabilityGrid` component is a static shell — busy slot rendering is not yet implemented.**
  The `busySlots` prop is accepted and passed correctly from `useEventBusySlots`, but the component never reads it. All cell coloring, overlap detection, and timezone conversion logic is deferred to Sprint 5. The data pipeline (hook → prop) is confirmed working.

- **Profile avatar in `Navbar` must use field names that actually exist on the stored user object.**
  Read `authStore.ts` to confirm exact field names before implementing avatar rendering. If `avatar_url` or `full_name` is null, fall back to the first letter of `email_address`. Mismatched field names cause the avatar to silently render nothing.

- **Unread notification count must be initialized from the fetched notification list, not only from real-time inserts.**
  The `notificationStore.unreadCount` starts at 0 and only increments via Supabase real-time subscription on new inserts. On page load, existing unread notifications are never counted. Fix: in `NotificationBell.tsx`, add a `useEffect` that runs when the notifications query resolves and calls `setCount(notifications.filter(n => !n.is_read).length)`. Add a `setCount` action to `notificationStore` if it does not exist.

- **Do not use `useState` + hook re-initialization to pass a dynamic URL segment to a mutation hook mid-flight.**
  In the create event form, the pattern of `useState<string | null>(null)` + `useInvite(createdEventUid ?? '')` + `setCreatedEventUid(event.uid)` inside `onSuccess` does not work — React state updates are asynchronous and the hook does not re-render before the mutation loop runs. Every invite fires against the empty string uid and fails silently. Fix: call `api.post(`/events/${event.uid}/invite`, { email })` directly inside `onSuccess` using the uid returned from the create mutation, bypassing the hook entirely.

- **Accept invitation should redirect to the event page, not stay on the current page.**
  After `takeAction` with `action='accept'` succeeds, the frontend should navigate to `/events/{event_uid}`. The notification object includes enough data (either `event_uid` directly or via metadata) to construct the URL. Declining should not redirect.
