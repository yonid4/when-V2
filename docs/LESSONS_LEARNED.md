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

- **Profile avatar in `Navbar` must use field names that actually exist on the stored user object.**
  Read `authStore.ts` to confirm exact field names before implementing avatar rendering. If `avatar_url` or `full_name` is null, fall back to the first letter of `email_address`. Mismatched field names cause the avatar to silently render nothing.

- **Unread notification count must be initialized from the fetched notification list, not only from real-time inserts.**
  The `notificationStore.unreadCount` starts at 0 and only increments via Supabase real-time subscription on new inserts. On page load, existing unread notifications are never counted. Fix: in `NotificationBell.tsx`, add a `useEffect` that runs when the notifications query resolves and calls `setCount(notifications.filter(n => !n.is_read).length)`. Add a `setCount` action to `notificationStore` if it does not exist.

- **Do not use `useState` + hook re-initialization to pass a dynamic URL segment to a mutation hook mid-flight.**
  In the create event form, the pattern of `useState<string | null>(null)` + `useInvite(createdEventUid ?? '')` + `setCreatedEventUid(event.uid)` inside `onSuccess` does not work — React state updates are asynchronous and the hook does not re-render before the mutation loop runs. Every invite fires against the empty string uid and fails silently. Fix: call `api.post(`/events/${event.uid}/invite`, { email })` directly inside `onSuccess` using the uid returned from the create mutation, bypassing the hook entirely.

- **Accept invitation should redirect to the event page, not stay on the current page.**
  After `takeAction` with `action='accept'` succeeds, the frontend should navigate to `/events/{event_uid}`. The notification object includes enough data (either `event_uid` directly or via metadata) to construct the URL. Declining should not redirect.

---

## Sprint 4 (Post-2) — Event Detail Rework & AvailabilityGrid

- **`isCoordinator` and `currentUserId` should be derived client-side from `authStore`, not server-side.**
  The original `EventDetailPage` (server component) made an extra `GET /api/auth/me` fetch to resolve the current user id, then passed `isCoordinator` and `currentUserId` as props to `EventDetailClient`. This adds a serial SSR fetch and duplicates logic that `authStore` already holds after login. The correct pattern: server component fetches only the event, client component reads `useAuthStore()` and derives coordinator status from `event.coordinator_id === user?.id`.

- **`GET /api/busy-slots/event/{uid}` must return 404, not `[]`, when the event does not exist.**
  The original router returned an empty list when the event lookup yielded no data. This masked bad event UIDs — callers could not distinguish "event has no participants yet" from "event does not exist". Changed to `raise HTTPException(404)` when `event.data` is falsy. Update any test that expected `[]` for an unknown uid to expect 404.

- **Filter busy slots server-side to the event time window — don't return all-time slots.**
  Without a filter, the busy slots query returns every synced calendar event for every participant across all time. For a grid covering a specific week, this produces enormous payloads. The fix: add `.lt("start_time_utc", latest).gt("end_time_utc", earliest)` to the Supabase query. Note the filter uses strict inequality (`lt`/`gt`), which correctly handles slots that partially overlap the window boundary.

- **`AvailabilityGrid` must be driven by the event's actual time window, not hardcoded hours.**
  The original grid hardcoded `hours = ['09:00 AM', ..., '05:00 PM']` and `days = ['MON', ..., 'FRI']`. This means any event outside 9–5 Mon–Fri was invisible. The grid now accepts `earliestTime` and `latestTime` UTC strings, derives `startHour`/`endHour` from them, and renders 7-day weeks with navigation. Always pass the event's actual `earliest_datetime_utc` / `latest_datetime_utc` as props.

- **Edit modal state should update local component state optimistically — avoid full page reloads after edits.**
  The original edit flow called `onSuccess: onClose` and left the displayed event data stale until the next page load. The fix: hold a `useState(initialEvent)` in `EventDetailClient`, pass an `onSave(result: EditSaveResult)` callback to `EditModal`, and merge the updated fields into local state after a successful mutation. This gives instant UI feedback without a round-trip.

- **Extract edit logic (`editSchema`, `computeEditDiff`, `toDatetimeLocal`) into a separate utility file.**
  Keeping the Zod schema, diff computation, and datetime conversion inside the 600-line `EventDetailClient.tsx` makes it hard to test in isolation. Moved to `app/events/[uid]/editEventUtils.ts`. These are pure functions with no React/DOM dependencies and can be unit-tested directly without rendering the component.

- **`allow_guest_invites` must be added as a column to the `events` table — it is not in the original schema.**
  The field was referenced in `types/index.ts` and the edit modal before the DB column existed. Migration: `alter table events add column allow_guest_invites boolean not null default false;`. Always add the column to `schema.sql` and run the migration before shipping code that reads or writes the field.

- **Stale busy slot deletion must use `end_time_utc`, not `start_time_utc`, as the upper bound when querying the DB.**
  Google's `timeMin=now` means any deleted event whose `start_time_utc` is in the past will not appear in Google's response — correctly. But if the DB query to find existing slots also uses `.gte("start_time_utc", now)`, those past-starting slots are excluded from the "existing" set and therefore never identified as stale. Fix: query the DB with `.lt("end_time_utc", time_max_iso)` only, with no lower bound. This catches any slot for the source that ended before the fetch horizon, regardless of when it started. Delete is then done by `provider_event_id` directly (scoped to `calendar_source_id`), not by slot `id`.

- **`useSyncMyCalendar` and `useSyncCalendar` serve different purposes — do not conflate them.**
  `useSyncMyCalendar` calls `POST /busy-slots/sync` and syncs only the current user's own calendar. `useSyncCalendar(uid)` calls `POST /busy-slots/sync/event/{uid}` and is coordinator-only (syncs all participants). The "Refresh" button in the actions panel should use `useSyncMyCalendar`; the coordinator "Sync All" button should use `useSyncCalendar`.

---

## Sprint 5 (Part A) — Busy Slot Rendering on the Grid

- **`getSlotsForCell` uses strict inequality on both boundaries — a slot ending exactly at cell start is not an overlap.**
  The overlap rule is `slot.start < cellEnd AND slot.end > cellStart`. A slot ending at exactly `10:00` when the cell starts at `10:00` is excluded. This matches the half-open interval `[cellStart, cellEnd)` convention used throughout the grid. Tests for both boundary conditions (`slotEnd === cellStart` and `slotStart === cellEnd`) must assert an empty result, not a match.

- **`getSlotsForCell` takes `Date` objects, not ISO strings — always construct cell boundaries before calling.**
  The helper signature is `(cellStartUtc: Date, cellEndUtc: Date, slots: SlotLike[])`. Inside the grid loop, construct `cellStartUtc` from the week start date + day offset + hour + half-row offset, then pass it and `cellEndUtc = cellStart + 30 minutes`. Do not pass raw ISO strings — `new Date(isoString) < new Date(isoString)` comparisons work, but the function contract expects `Date` objects.

- **Intensity scaling for busy/preferred cells uses participant count, not a fixed threshold.**
  The `busyClass` and `preferredClass` helpers scale opacity by how many participants' slots overlap the cell (`busyCount` / `preferredCount`). The thresholds implemented are: `< 3 → /20`, `>= 3 → /40`, `>= 5 → /65`, `>= 7 → /90`. These differ from the sprint plan spec (`1 → /30`, `2 → /55`, `3+ → /80`) — the plan assumed a small fixed participant count; the implementation uses the actual count and spreads the scale wider. Update the sprint plan spec if the visual result is accepted.

- **Conflict cells render as a flex row with two half-width divs — do not use CSS `background: linear-gradient`.**
  The conflict split (left half red, right half green) is implemented as `<div className="flex w-full h-full"><div className="w-1/2 h-full {busyClass}" /><div className="w-1/2 h-full {preferredClass}" /></div>`. A CSS gradient would not respond to the dynamic intensity classes. The "CONFLICT" label is absolutely positioned and centered over both halves.

- **Busy and conflict cells must be `cursor-default` in all modes, including edit mode.**
  When edit mode is added in Part C, the pointer style for empty cells will change to `crosshair`. Busy/conflict cells must explicitly stay `cursor-default` (not `cursor-not-allowed` as the spec says) to avoid implying the cell is interactive but blocked. The `not-allowed` cursor is reserved for the drag-over-busy-slot overlay if needed.

- **`lib/api.ts` must handle both 401 and 403 as "unauthenticated" — `HTTPBearer` returns 403 when no Authorization header is sent.**
  The original `api.ts` only cleared the token and redirected on 401. But FastAPI's `HTTPBearer` returns 403 (not 401) when the `Authorization` header is completely absent. If the token is missing from `localStorage` (e.g. expired session, cleared storage), client-side requests have no header at all — backend returns 403 — and `api.ts` used to treat this as a generic error rather than redirecting to login. Fix: `if (res.status === 401 || res.status === 403)` in the error branch of `lib/api.ts`.

- **Remove `console.log` statements from `AvailabilityGrid` before Part B — they fire on every render.**
  The grid logs `busySlots received`, `first cell`, and individual slot comparisons on every render cycle. These were left in for debugging during Part A. Remove before wiring real preferred slots in Part B or the console will be flooded.

- **`SlotLike` interface in `gridUtils.ts` must match the shape used by both `busySlots` and `preferredSlots`.**
  Both slot types share `{ start_time_utc: string, end_time_utc: string, user_id: string }`. The `SlotLike` interface in `gridUtils.ts` is the canonical shape. `EventDetailClient` defines a local `SlotItem` type that is structurally identical — these can be unified by importing `SlotLike` directly from `gridUtils.ts` instead of duplicating the definition.

---

## Sprint 5C — Edit Mode Drag & Resize Fixes

- **Pass `cellStartUtc: Date` through `onCellMouseEnter` — never recompute from rowIndex in the parent.**
  The `AvailabilityGrid` already has `cellStartUtc` computed correctly for each cell (using `weekOffset` from its internal state). If you instead pass `rowIndex` up and try to reconstruct the date in the parent with `rowIndexToStartDate(dragState.baseDate, dayIndex, rowIndex)`, the parent's `baseDate` does not know about the current `weekOffset`, so dates will be wrong for any week other than week 0. Fix: change `onCellMouseEnter` to accept `cellStartUtc: Date` and use it directly in the drag/resize handlers.

- **`dragState.baseDate` must be derived from `cellStartUtc`, not from `event.earliest_datetime_utc`.**
  The original `handleCellMouseDown` computed `baseDate` from `event.earliest_datetime_utc` (always week 0's Monday). When the user is viewing a different week, `baseDate` was wrong, making `runMergeCheck`'s `getDayIndex` function return `-1` for all slots. Fix: derive `baseDate` from `cellStartUtc` itself — set hours to 0, then back up to Monday of that cell's week: `baseDate.setDate(baseDate.getDate() - (dayOfWeek + 6) % 7)`.

- **Resize `baseDate` must be derived from `pendingSlot.startUtc`, not `dragState.baseDate`.**
  During a resize, `dragState` is null (the user is not dragging a new slot — they are resizing an existing one). The original `handleDocumentMouseUp` called `runMergeCheck(..., dragState.baseDate)` which would throw at runtime because `dragState` was null. Fix: in the resize branch of `handleDocumentMouseUp`, derive `baseDate` from `pendingSlot.startUtc` the same way as in `handleCellMouseDown`.

- **`pointer-events: none` on the pending slot overlay is required so mouse events fall through to cells during drag.**
  When the pending slot renders as an absolute overlay div on top of a preferred-count cell, that overlay div must have `pointer-events-none`. Without it, `onMouseEnter` on the underlying cell div fires once (when the mouse first enters the cell), but subsequent movements within the cell are absorbed by the overlay, preventing drag extension from working on cells already covered by the pending slot. This applies to any decorative overlay added on top of a cell that needs to remain draggable.

- **`e.stopPropagation()` on resize handle `onMouseDown` is required to prevent triggering cell drag.**
  Resize handles (top/bottom edge of the pending slot) are child elements inside the cell div. The cell div also has `onMouseDown` to start a drag. Without `e.stopPropagation()` on the handle's `onMouseDown`, both the handle and the cell fire — the cell's handler runs first in bubble phase and sets `dragState`, which immediately clobbers `resizeState` and starts a new drag instead of a resize. `stopPropagation` on the handle prevents this.

- **Add `onMouseEnter` to resize handle divs in addition to the cell itself.**
  The cell's `onMouseEnter` fires when the mouse first enters the cell element. If the mouse enters a resize handle div (a child) without having been over the cell first, the cell's `onMouseEnter` does not re-fire. Since the handle is positioned at the very top or bottom edge, fast cursor movement can land directly on the handle. Wiring `onMouseEnter` on the handle div itself (in addition to the cell) ensures every entry point triggers the drag/resize extension logic.

## Sprint 5C — Conflict/Busy/Preferred Overlay Rendering

- **Busy and preferred overlays must be clipped to their non-conflict segments before rendering.**
  Rendering full-bounds busy/preferred divs underneath a z-20 conflict overlay causes two problems: (1) the busy/preferred background color bleeds into the conflict zone visually (the conflict block's visual boundary is muddied by the color underneath it), and (2) the label centers relative to the full original div height, landing at the midpoint of the full span rather than the visible non-conflict portion. Fix: use `subtractConflicts(overlay, conflicts)` to split each overlay into its visible non-conflict segments. Render one independent div per segment, each with its own geometry, rounded corners, overflow-hidden, and label centered to its own height. The conflict overlay renders separately as before (z-20, split block, no changes).

- **The `overlayStyle` helper adds a 2px vertical gap (top + 2, height − 4) to every slot overlay.**
  Adjacent slots that touch at their boundaries (e.g. preferred ending at 09:30, conflict starting at 09:30) would otherwise render as flat edges against each other with no visual separation. The 2px gap keeps rounded corners fully visible and ensures adjacent blocks never visually merge. The gap applies to all slot types (busy, preferred, conflict, pending) via `overlayStyle`.

- **Show the time label for any segment ≥ 30 minutes, not ≥ 60 minutes.**
  The initial label-visibility threshold was 60 minutes (2 rows). A 30-minute segment (1 row) is a common real-world case (e.g. a preferred slot outside the conflict zone) and is tall enough to display its time range. Threshold is `seg.endUtc - seg.startUtc >= 30 * 60 * 1000`.
