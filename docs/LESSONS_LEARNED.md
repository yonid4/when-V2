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
  Browser anchor navigation does not send the `Authorization: Bearer` header. The fix: add a `GET /api/calendar-accounts/connect-url` endpoint that returns `{ url }` as JSON, then redirect from the frontend using `window.location.href = url` after fetching with `api.get(...)`. The original redirect-based `/connect` endpoint was retained for one cycle and removed in the post-launch cleanup pass once it was confirmed to have no remaining callers.

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

---

## Sprint 5D — Preferred Slot Deletion (Click to Remove)

- **Render the display overlay and the click overlay as two separate layers — do not conflate them.**
  The preferred slot display overlays are merged across all users' slots (using `mergeSlots`) so intensity scales with participant count. Click handling requires knowing the individual DB slot ID, which is lost after merging. Fix: keep the merged display overlays for visual rendering (pointer-events: none), then render a second set of transparent, full-geometry click overlays for only the current user's own slots (z-index: 25, pointer-events: auto) on top. Two layers, two concerns.

- **The click overlay must span the full slot geometry — not be clipped to non-conflict segments.**
  Clipping the clickable overlay with `subtractConflicts` means the user cannot click the portion of their preferred slot that overlaps a conflict block. Since the conflict overlay is z-20 and the click overlay is z-25, the click overlay can sit safely above the conflict block and still register clicks across the full slot height.

- **In edit mode, clicking an own preferred slot must add it to `slotsToDelete` and remove it from `displayedPreferredSlots` — but only after confirmation.**
  The initial implementation immediately removed the slot on click without asking. The correct flow matches view mode: show the "Remove this slot?" confirmation popover first. On confirm, add to `slotsToDelete` and filter it out of `displayedPreferredSlots` (optimistic removal). The slot is physically deleted from the DB only when the user later clicks Done (same `handleDone` flow that processes all pending deletions).

- **Slots already in `slotsToDelete` must be excluded from the clickable overlay.**
  Once a slot is marked for deletion (via either the click-to-delete flow or the merge flow), its overlay is no longer visible in `displayedPreferredSlots`. The own-slot click overlay filter must also exclude them — `!(isEditMode && slotsToDelete.includes(s.id))` — to prevent a ghost clickable region over a slot that visually no longer exists.

- **`deletingSlotId` state and the Escape key handler live in the main component, not in `AvailabilityGrid`.**
  The confirmation logic (`deletingSlotId`, `onSlotClick`, `onSlotDeleteConfirm`, `onSlotDeleteCancel`) is driven by the parent `EventDetailClient`. `AvailabilityGrid` receives these as props and renders the confirmation UI inline on the overlay div. Keeping the state in the parent ensures cancel/confirm can trigger parent-level actions (e.g. `setSlotsToDelete`, `deletePreferredSlot`) without callback threading through multiple grid levels.

- **Clicking elsewhere on the grid column must dismiss the confirmation — add `onClick` to the column div.**
  The column div (`<div key={di} className="flex flex-col relative ...">`) receives an `onClick` that calls `onSlotDeleteCancel()` when `deletingSlotId` is set. The confirmation div itself calls `e.stopPropagation()` so clicks within the popover do not dismiss it. Combined with the Escape key handler in the parent, this covers both pointer and keyboard dismissal.

---

## Sprint 6A — Slot Rendering

- **Slot overlays must be clipped to the grid's visible time bounds before computing geometry and labels.**
  Slots from the DB may span outside the event window (e.g. an all-day Google Calendar event or a busy slot starting at 08:00 on a 09:00–17:00 grid). Always clip `startUtc`/`endUtc` to `colDayStart`/`colDayEnd` per column before calling `overlayStyle()` and before rendering time labels. If the clipped end ≤ clipped start, skip rendering entirely. The clipped times are used only for rendering — do not mutate the original slot data. The pending slot is built from grid cell coordinates so it is always in bounds and needs no clipping.

## Sprint 5E — Preferred Slot Edit Mode Hardening

- **Pass only the current user's own slots to `runMergeCheck` — never all participants' slots.**
  `computeMerge` determines which existing preferred slots overlap the pending drag slot and marks them for deletion. If all participants' slots are passed in, foreign users' slot IDs end up in `slotsToDelete` and the `handleDone` call tries to DELETE them, hitting a 403. Fix: filter to `ownSlots = preferredSlots.filter(s => s.user_id === user?.id)` at both `handleDocumentMouseUp` call sites (drag branch and resize branch) before calling `runMergeCheck`.

- **Re-append foreign slots to `displayedPreferredSlots` inside `runMergeCheck` after every merge.**
  `computeMerge` only returns `remainingSlots` from the set it was given (own slots). If you set `displayedPreferredSlots` to `result.remainingSlots` directly, foreign users' slots disappear from the grid mid-drag. Fix: derive `foreignSlots` from the full `preferredSlots` list (filtering to `user_id !== user?.id`) and spread them in: `setDisplayedPreferredSlots([...result.remainingSlots, ...foreignSlots])`.

- **Use `Promise.allSettled` instead of `Promise.all` for batched preferred slot deletes in `handleDone`.**
  `Promise.all` short-circuits and throws on the first rejection. If a 403 arrives (e.g. a foreign slot id slipped into `slotsToDelete`), the entire batch is aborted and the UI is left in a broken state. `Promise.allSettled` collects all outcomes; check `.filter(r => r.status === 'rejected').length` and surface a single error message if any failed. This is the defensive fallback — the root cause (foreign ids) is fixed by the own-slot filter above, but `allSettled` prevents silent partial failures.

- **Gate the own-slot interactive (click-to-delete) overlay on `isEditMode`.**
  In view mode the click overlay should not exist — clicking a preferred slot should do nothing. The overlay render block for own slots must be wrapped in `{isEditMode && ...}`. In view mode, the separate click overlay that handles deletion (Part D) is still active; only the edit-mode overlay (which adds to `slotsToDelete` rather than calling the API directly) should be gated.

- **`computeMerge` overlap condition must use `<=`/`>=` so touching boundaries merge.**
  Original: `startUtc < slotEnd && endUtc > slotStart` (strict). This excluded slots that touch at exactly one boundary point — a preferred slot ending at 10:00 and a pending slot starting at 10:00 were not merged, leaving a 0-width gap between them. Fix: `startUtc <= slotEnd && endUtc >= slotStart`. Adjacent slots that share a single boundary instant are now merged into one continuous block. Update the corresponding test case: "merges adjacent slots that touch at a boundary" now expects `slotsToDelete` to have length 1 (not 0).

- **Dot indicators for own preferred slots must be rendered per original DB slot, not per merged display segment.**
  The first attempt rendered a dot inside each merged `preferredOverlays` segment and checked whether the current user's slot overlapped it. This failed for partial overlaps — the dot was skipped when the own slot only covered part of the segment. Fix: render a completely separate set of dot divs, one per own preferred slot, each using `clipToGridBounds(s.start_time_utc, s.end_time_utc, ...)` for geometry. These divs are `pointer-events: none` so they never interfere with drag or click handlers.

- **Preferred slot color density must reflect per-region participant count, not the whole merged block's max count.**
  The initial implementation used `mergeSlots(colPreferred)` which collapsed all overlapping slots into one merged block and assigned the max participant count to the entire span. This made a 1-participant region that happened to be adjacent to a 4-participant region render at 4-participant intensity. Fix: replace with `buildCountedSegments(colPreferred)` which splits slots at every boundary point, counts coverage per segment, then re-merges adjacent segments that fall in the same density bucket (1–2, 3–4, 5–6, 7+). Only crossing a bucket boundary creates a visual split.

- **`buildCountedSegments` merge condition must use `preferredIntensityClass` equality, not raw count equality.**
  If two adjacent segments have counts 1 and 2 (both in the 1–2 bucket), they should render as one block at the same color — splitting them creates a visible seam at the same intensity. Using `preferredIntensityClass(raw[i].count) === preferredIntensityClass(last.count)` as the merge key collapses same-bucket adjacent segments correctly. When merging, keep the higher count: `if (raw[i].count > last.count) last.count = raw[i].count` — this ensures `preferredIntensityClass` computed from the merged segment's stored count still maps to the correct bucket.

---

## Sprint 6A — Scheduling Algorithm & Proposals

- **Patch `service_client` in both the router module AND the service module.**
  When `proposal_service.py` does `from app.utils.supabase import service_client`, Python binds that name locally in `proposal_service`'s namespace. Patching `app.routers.proposals.service_client` does NOT affect the service module's binding — both must be patched separately. Use two `@patch` decorators: `@patch("app.routers.proposals.service_client")` and `@patch("app.services.proposal_service.service_client")`. The same principle applies to any module that imports `service_client` at the top level.

- **`db.table.side_effect` creates a fresh `MagicMock()` every invocation — you cannot introspect a specific table mock via `db.table("name")` after the test.**
  Using `db.table.side_effect = lambda name: MagicMock()` means calling `db.table("proposed_times")` after the test creates a brand-new mock that was never called, so `call_args` is always `None`. Fix: create the mock before `make_table`, reference it inside the lambda, and inspect THAT variable directly post-test:
  ```python
  proposed_times_mock = MagicMock()
  def make_table(name):
      if name == "proposed_times": return proposed_times_mock
      ...
  db.table.side_effect = make_table
  # after generate_proposals():
  inserted = proposed_times_mock.insert.call_args[0][0]
  ```

- **`useProposals` uses a POST request, not GET.**
  The proposals endpoint (`POST /events/{uid}/proposals`) accepts filter params via the request body (future extensibility). The hook calls `api.post(...)`. In tests, mock `api.post`, not `api.get`.

- **Lazy-loading proposals with an `enabled` boolean prevents unnecessary backend calls.**
  Rather than fetching proposals on page load (slow, expensive), the `useProposals(uid, enabled)` hook only fires when `enabled=true`. The "View Proposed Times" button flips `proposalsEnabled` state — on first click the query runs, on subsequent views the cache is reused. This also prevents generating proposals before the user asks for them.

---

## Sprint 6B — Event Finalization

### Backend

- **Three `@patch` decorators required for finalize tests: service, dep, and GCal.**
  `finalize_service.py` imports `service_client` at load time AND imports `build` from `googleapiclient.discovery`. All three must be patched at their import site in the service module:
  ```python
  @patch("app.services.finalize_service.build")
  @patch("app.services.finalize_service.service_client")
  @patch("app.dependencies.service_client")
  ```
  Patching `googleapiclient.discovery.build` directly does NOT affect the already-bound name in `finalize_service`.

- **`calendar_sources` write-cal filter is Python-side, not SQL.**
  `finalize_service.py` queries `calendar_sources` with only `.eq("is_write_calendar", True)` (no user_id filter in SQL), then loops through results to find the row whose `calendar_accounts.user_id` matches `current_user.id`. The mock chain for `calendar_sources` is therefore `.select().eq().execute()` — just one `.eq()` call.

- **DB update is intentionally deferred until after successful GCal API call.**
  The service calls `events().insert(...).execute()` first, then writes the event update and notifications. If `HttpError` is raised, the except block raises 502 without touching the DB. Tests for the 502 case should verify `mock_svc_svc.table("events").update` was never called.

- **`HttpError` requires a mock response with `.status` and `.reason` attributes.**
  `googleapiclient.errors.HttpError.__init__` reads `resp.status` and `resp.reason` synchronously. Use a plain `Mock()` (not `MagicMock()`) with those attributes set explicitly:
  ```python
  mock_resp = Mock()
  mock_resp.status = 403
  mock_resp.reason = "Forbidden"
  HttpError(resp=mock_resp, content=b"error")
  ```

- **`calendar_accounts` credentials query uses two `.eq()` calls.**
  The query filters by both `user_id` and `provider="google"`. Mock chain depth: `.select().eq().eq().maybe_single().execute()`. If only one `.eq()` is mocked, the second call returns a fresh `MagicMock()` whose `.maybe_single().execute().data` will not be the expected dict.

### Frontend

- **`act()` wrapper is required when triggering mutations in `renderHook` tests.**
  Calling `result.current.mutate(...)` inside `renderHook` without `act()` causes React state update warnings and flaky assertions. Always wrap the mutation call:
  ```typescript
  await act(async () => {
    result.current.mutate({ proposed_time_id: 'pt-uuid-1', note: 'See you there!' })
  })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  ```

- **Supabase real-time subscription for events UPDATE must filter on the DB row `id`, not the public `uid`.**
  The `events` table has both `id` (integer PK / UUID) and `uid` (public slug). Supabase real-time `filter` expressions use the actual column name. Use `id=eq.${event.id}` (the internal DB id) so the filter matches the row that Supabase sends in the change payload.

- **`event_finalized` notification messages should render the finalized time in the user's local timezone, not the raw `n.message` string.**
  The backend sets `n.message = "The event time has been confirmed."` (generic). The actual time is in `n.metadata.finalized_start_time_utc` / `finalized_end_time_utc`. `NotificationList` checks `n.notification_type === 'event_finalized'` and calls `getFinalizedMessage(n)` which formats the UTC times into a local-timezone string (e.g. "Mon, Apr 10 at 12:00 PM – 1:00 PM"). Always check `n.metadata` for richer display data before falling back to `n.message`.



---

## Sprint 6C — Finalize Event Card

### Backend

- **`event_participants` table is queried twice in `finalize_event` — once for accepted participants, once for the coordinator.**
  Build separate mock branches by call count (`_ep_call_count`). The first call returns the full accepted list; the second returns only the coordinator row via `maybe_single()`. Both chains (`.select().eq().eq().execute()` and `.select().eq().eq().maybe_single().execute()`) must be configured on each mock.

- **Coordinator is always added to attendees, even if not in `event_participants`.**
  The service has a two-step fallback: first look up coordinator in `event_participants`; if absent (e.g. coordinator never RSVPed), fall back to `profiles` table. Tests must exercise both paths.

- **`location` key is omitted from the GCal `event_body` when empty, not set to `None`.**
  The code does `if location: event_body["location"] = location`. This means a missing `location` key is different from `location=None`. Tests that verify GCal body shape must use `assertIn`/`assertNotIn` on the key, not assert the value is None.

- **`name` update in DB is conditional on whether name changed.**
  `update_payload["name"]` is only added when `name != event["name"]`. When they are the same, the `name` key is absent from the payload entirely — not set to the same value. Tests that cover this must assert `.update.call_args` includes or excludes the `"name"` key accordingly.

### Frontend

- **Remove dead FinalizeModal rather than leaving it.** Once FinalizeCard replaced FinalizeModal, the old inline function was deleted to avoid a stale `useFinalize` import. Keeping unused components with hook calls causes lint/TS warnings and can confuse future sessions.

- **Coordinator checkbox in FinalizeCard is always locked checked.** The coordinator is always invited to their own event and cannot be excluded. The `disabled` checkbox prevents toggling, backed by a guard `!isCoord && toggleParticipant(...)` in the onChange handler.

---

## Bug Fixes (Pre-Modularization)

### Frontend

- **`router.refresh()` must be called before `router.push()` to bust the Next.js RSC cache after a mutation.**
  After deleting an event (or any mutation that changes server state), calling only `router.push('/dashboard')` navigates to the dashboard but the page is served from the RSC cache — the deleted event still appears. Calling `router.refresh()` first invalidates the Next.js server-side cache so the next navigation fetches fresh data. The correct pattern is always `router.refresh(); router.push('/dashboard')` when navigating away after a destructive mutation.

- **Tailwind dynamic class names are purged at build time — always use a static mapping object, never string interpolation.**
  Writing `className={\`bg-${color}-100 text-${color}-700\`}` produces class strings that Tailwind's build step never sees, so the styles are absent in production. The fix is a static `Record<string, string>` mapping each possible value to the full class string (e.g. `meeting: 'bg-blue-100 text-blue-700'`). Tailwind can only include classes that appear as literal strings in the source. Any time badge/chip colors are driven by a runtime value, use a lookup object.

### Backend

- **Supabase RLS blocks `anon_client` (the authed user client) from reading other users' `profiles` rows — use `service_client` for cross-user profile lookups.**
  When fetching event participants, the single-query join `event_participants(..., profiles(full_name, avatar_url, email_address))` worked only for the calling user's own profile because RLS on the `profiles` table restricts reads to `id = auth.uid()`. Other participants' profile rows were silently omitted, causing avatar initials to fall back to `?`. The fix is a two-query pattern: fetch `event_participants` with `get_authed_client` (respects RLS correctly for that table), then fetch `profiles` separately using `service_client` (bypasses RLS). Backend tests for this pattern must also patch `app.services.event_service.service_client` and return flat ep rows without a nested `profiles` key.

- **FinalizeBody must include all 7 fields in tests.** After expanding the hook body type, tests that only pass `{ proposed_time_id, note }` will now fail TypeScript (object literal with missing required fields). Update test fixtures to always include the full `baseFinalizeBody` spread + overrides.

---

## Sprint 7 — Bug Fixes (Invitation Accept Redirect & Gmail Normalization)

### Backend

- **`PUT /api/invitations/{id}/respond` should return the event uid on accept, not 204.**
  The original endpoint returned HTTP 204 (no body). The frontend had no way to know which event to redirect to after accepting. The fix: change `respond_to_invitation` to return the event `uid` (string) on accept, `None` on decline. The router endpoint now returns `InvitationRespondResponse(event_uid=...)` with a 200 status. The `InvitationRespondResponse` Pydantic model has a single nullable field `event_uid: str | None = None`.

- **`respond_to_invitation` must select `uid` from the events row, not just `coordinator_id` and `name`.**
  The coordinator notification query was `select('coordinator_id, name')`. To also return the event uid, update it to `select('coordinator_id, name, uid')` and `return event.get('uid')` before the function falls through to `return None`.

- **Gmail dot normalization: strip dots from local part for `@gmail.com` only.**
  Gmail treats dots in the local part as insignificant (`john.doe@gmail.com` = `johndoe@gmail.com`). Add a `normalize_email(email: str) -> str` helper in `app/utils/email.py`: partition on `@`, strip dots from `local` only when `domain.lower() == 'gmail.com'`. Apply in `auth_service._upsert_profile` (profile creation) and `invitation_service.invite_by_email` (first line). Non-Gmail addresses are returned unchanged.

- **Apply `normalize_email` in `auth_service` at two call sites: profile upsert AND pending invitation processing.**
  `_upsert_profile` writes the email to `profiles.email_address`. `exchange_code_and_upsert_user` later calls `_process_pending_invitations(profile["id"], email)`. Both must use `normalize_email(user_info["email"])` so that a pending invitation for `johndoe@gmail.com` is matched when the user signs in with `john.doe@gmail.com`.

### Frontend

- **Accept button in `NotificationList` must call `useRespondToInvitation` directly — not `useTakeAction`.**
  The old flow: accept button → `POST /notifications/{id}/action` → backend internally calls `respond_to_invitation` → notification service re-fetches notification with join → extracts `event_uid`. This had two failure points: (1) the update response from Supabase has no `events` join, so `event_uid` was null after the update; (2) even after the re-fetch fix the indirection added complexity. The new flow: accept button → `PUT /api/invitations/{id}/respond` → backend returns `{ event_uid }` directly → frontend redirects. The `invitation_id` lives in `n.metadata.invitation_id`.

- **The decline button in `NotificationList` must also switch to `useRespondToInvitation` (same hook).**
  Both accept and decline now call `respondToInvitation({ invitationId, action })`. Guard with `if (!invitationId) return` since `metadata.invitation_id` could theoretically be absent. Decline continues to not redirect.

- **`useTakeAction` is no longer needed by `NotificationList` — remove the import to avoid dead code.**
  After switching to `useRespondToInvitation`, `useTakeAction` had no callers in `NotificationList.tsx`. Remove the import from both the component and check if `useTakeAction` is still exported from `useNotifications.ts` for any other consumer. If not used anywhere, remove the export too.

- **`useRespondToInvitation` return type must be `{ event_uid: string | null }`, not `void`.**
  The hook was originally typed `api.put<void>(...)`. After the backend change, update it to `api.put<{ event_uid: string | null }>(...)`. The `onSuccess` callback receives `data` and constructs the redirect URL: `data?.event_uid ? \`/events/${data.event_uid}\` : '/dashboard'`.

- **Invalidate `['participants']` in `useRespondToInvitation.onSuccess` — the user just joined the event.**
  The hook previously only invalidated `['notifications']` and `['events']`. After accepting, the user is added to `event_participants`. Any cached participants list for that event is now stale. Add `queryClient.invalidateQueries({ queryKey: ['participants'] })` to `onSuccess`.

---

## Sprint 8 — Sync Service: Stale Deletion Fix

### Backend

- **Build `fetched_event_ids` from `all_items` directly, not from `slots_to_upsert`.**
  The stale deletion set was built as `{s["provider_event_id"] for s in slots_to_upsert}`. This meant events that were filtered out during slot construction (missing datetimes, all-day events) were absent from `fetched_event_ids` — those DB rows would incorrectly be treated as stale and deleted. More critically, it meant the set was computed from the already-filtered list rather than from the raw Google API response. The fix: collect `fetched_event_ids` in the item loop itself, before the slot-construction filters.

- **Cancelled Google Calendar event instances (`status == "cancelled"`) must be excluded from `fetched_event_ids` — not just from `slots_to_upsert`.**
  Google returns cancelled event instances in some responses (e.g. recurring events with deleted occurrences). If a cancelled item's `id` is added to `fetched_event_ids`, the corresponding DB row is never treated as stale and is never deleted. The correct behavior: skip cancelled items at the top of the loop — add neither to `slots_to_upsert` nor to `fetched_event_ids`. Any existing DB row for the cancelled event id is then identified as stale and deleted.

- **The stale deletion delete call must be skipped entirely when `stale_event_ids` is empty.**
  The implementation gates the delete behind `if stale_event_ids:` — this is intentional and must be preserved. Running `.delete().eq(...).in_("provider_event_id", [])` against Supabase with an empty list produces undefined behavior (may delete all rows for the source). Tests must assert `mock_svc.table.return_value.delete.assert_not_called()` when no stale slots exist.

---

## Modularization — Model Polish

### Backend

- **`notification_type` Literal must include `'invite_accepted'` — the task spec listed only three values but a fourth is actively used.**
  The modularization task specified `Literal['event_invitation', 'event_finalized', 'event_deleted']` for `NotificationResponse.notification_type`. However, `invitation_service.py` writes `notification_type='invite_accepted'` rows when invitations are accepted. Adding a Literal that omits an in-use value would cause runtime Pydantic validation errors for every accepted invitation notification. Always grep for actual values before tightening a `str` field — the grep is: `grep -r "notification_type" backend/app/services/ --include="*.py"`.

- **Pydantic V2 auto-coerces ISO strings to `datetime` fields — no caller changes needed when tightening DB-mapped models.**
  Changing `BusySlotResponse.start_time_utc` / `end_time_utc` from `str` to `datetime`, and `CalendarSourceResponse.created_at` / `updated_at` from `Optional[str]` to `datetime | None`, did not require any changes in `calendar_service.py`. Pydantic V2 parses ISO strings (as returned by Supabase) automatically when the declared field type is `datetime`. All 137 backend tests passed after the change with no modifications to callers.

- **`proposal_service.py` DB column / API field split is already consistent — no bug found.**
  The task suspected a mismatch between the DB column name `conflicts` and the frontend-expected field `conflict_count`. On inspection, both `get_cached_proposals` and `generate_proposals` already read the DB column `conflicts` and map it to the key `conflict_count` in every returned dict, and `ProposalResponse` uses `conflict_count: int`. The split is intentional and correct — DB stores `conflicts`, API exposes `conflict_count`.

- **`models/participant.py` was already fully tightened in a prior sprint — Task 5 was a no-op.**
  `ParticipantStatus` and `RsvpStatus` were already `Literal` types, `status` was already `ParticipantStatus`, and `rsvp_status` was already `RsvpStatus | None`. The grep confirmed `'pending'` is a valid in-use value (included in the Literal). No changes needed.

---

## Modularization — HTTPException Migration

### Backend

- **The three-condition rule: only migrate an HTTPException to the router if all three hold.**
  (1) The service function is called by exactly one router. (2) The router does not already handle the same error case. (3) Moving it does not require duplicating the check in multiple callers. Fail any condition → leave the exception in the service.

- **The disambiguation problem: `return None` is useless when a service raises multiple distinct status codes.**
  When a service function can raise both 403 and 404, replacing both with `return None` loses the status code. The router can't know which to use. Any function that raises more than one distinct status code must keep its exceptions in the service.

- **Single-error-code functions with a single caller are always safe to migrate.**
  `create_event` (500 only), `get_finalize_status` (403 only), `disconnect_account` (403 only), `get_event_busy_slots` (403 only), `get_event_for_coordinator_sync` (403 only) — all moved. Service returns `None`; router raises with the one known status code.

- **`respond_to_invitation` fails Condition 1 — called by both a router and another service.**
  `invitation_service.respond_to_invitation` is called by `routers/invitations.py` AND by `notification_service.take_action`. Multiple callers → all exceptions stay in the service. Always grep all callers before migrating: `grep -r "respond_to_invitation" backend/app/ --include="*.py"`.

- **`sync_service.py` had no HTTPExceptions at all — nothing to migrate.**
  The service returns data directly and lets callers handle the logic. Worth noting because it proves the final architecture is achievable without HTTPExceptions in services.

- **The migration pattern for `bool` returns (vs `None`).**
  For functions that return nothing on success (e.g. `disconnect_account`), use `-> bool` instead of `-> None | something`. Service returns `True` on success, `False` on error. Router checks `if not ok: raise HTTPException(...)`. Cleaner than a typed sentinel value.

---

## Sprint 9 — Polish, Performance & Real-time Completion

### Testing Async Server Components in Vitest / jsdom

- **`cookies()` from `next/headers` throws "called outside a request scope" in jsdom — mock it at the `vi.mock` level.**
  Next.js server APIs (`cookies()`, `headers()`) depend on the Next.js request context, which does not exist in jsdom. Any test that imports a page component that calls `cookies()` will throw before rendering. Fix: `vi.mock('next/headers', () => ({ cookies: vi.fn().mockResolvedValue({ get: () => ({ value: 'test-token' }) }) }))`. This resolves synchronously and the component never hits the real API.

- **Await the async server component to get its resolved JSX before passing to `render()`.**
  Async server components are async functions that return JSX. `render(DashboardPage)` does not work — you must `await` the component first: `const jsx = await DashboardPage(); render(jsx)`. This is the correct pattern for testing Next.js async server components in Vitest without a real request context.

- **Mock per-route `fetchers.ts` files, not the hooks they replaced.**
  After converting a page from a `'use client'` hook-driven component to an async server component, any test that mocked `useEvents` must switch to mocking `fetchEvents` from the new `fetchers.ts`. The component no longer calls the hook at all, so the hook mock is silently ignored — the test passes but is testing nothing. Always trace the actual data path after an SSR conversion.

### Modularization — `fetchers.ts` Pattern

- **Extract all server-side fetch helpers into co-located `fetchers.ts` files, not inline in page components.**
  Each page route directory that performs SSR data fetching should have a `fetchers.ts` alongside `page.tsx`. The page file stays declarative (auth check → data fetch → render). This makes the fetch functions independently testable and keeps page files short. Pattern: `app/dashboard/fetchers.ts` exports `fetchEvents(token)` and `fetchCalendarAccounts(token)`; `app/events/[uid]/fetchers.ts` exports `fetchEvent(uid, token)`.

- **SSR fetch helpers return empty arrays / null on failure — no separate error state.**
  Server components cannot propagate an `isError` boolean to the page JSX the way TanStack Query does. The `fetchers.ts` pattern wraps all fetches in try/catch and returns `[]` or `null` on any non-200 response. The page renders an empty state rather than an error state. Remove any "error state" tests that depended on `useEvents`'s `isError` — they no longer apply.

### TypeScript — Partial `UseQueryResult` Mocks

- **Partial `UseQueryResult` objects require `as unknown as ReturnType<typeof hook>` to satisfy TypeScript.**
  `UseQueryResult<T>` has ~20 required fields. When mocking a hook in tests with only `{ data, isLoading }`, TypeScript rejects the cast. The correct pattern is `vi.mocked(useHook).mockReturnValue({ data: ..., isLoading: false } as unknown as ReturnType<typeof useHook>)`. The double cast (`as unknown` first) bypasses structural type checking while keeping the mock readable.

### `ProposalResponse` Type — Field Rename

- **`ProposalResponse.score` was replaced by `conflict_count` and `preferred_count` in Sprint 8 — update test fixtures.**
  The Sprint 8 modularization changed the proposal response shape: `score: number` was removed; `conflict_count: int` and `preferred_count: int` were added as separate fields. Any test fixture using `score: 0.9` will fail with "Object literal may only specify known properties". Replace with `conflict_count: 0, preferred_count: 3` (or whatever values apply). When updating tests after a type change, always grep `ProposalResponse` usages before writing fixtures.

---

## Post-Sprint 9 — Final Touches & Realtime Hardening

### Backend

- **`supabase-py` + `h2` package causes `RemoteProtocolError` drops — force HTTP/1.1 on every client.**
  When the `h2` package is installed, `httpx` (used internally by `supabase-py`/`postgrest-py`) negotiates HTTP/2 by default. Supabase's PostgREST drops HTTP/2 connections mid-stream, raising `httpx.RemoteProtocolError`. Fix: add a `_force_http1` helper in `app/utils/supabase.py` that replaces `client.postgrest._session` with `httpx.Client(http2=False)`. Apply it to `anon_client`, `service_client`, and the client returned by `get_authed_client`. No router or service changes needed.

- **Google OAuth callback must forward the `state` parameter to `exchange_code_and_upsert_user`.**
  The `/auth/callback` router was not passing the `state` query param to the service function. When Google returns a non-default state value, `flow.fetch_token` fails its internal state check. Fix: accept `state: str | None = None` as a query param in the callback handler and pass it through. Add `logger.error(..., exc_info=True)` inside `fetch_token` to surface failures that were previously swallowed.

- **Auth tests must use a real `google.oauth2.credentials.Credentials` object, not a plain `MagicMock`.**
  `auth_service.py` inspects `.token` and `.refresh_token` on the flow credentials object, and later serializes them via `google.oauth2.credentials` methods. A raw `MagicMock()` passes attribute reads but breaks serialization. Fix: `from google.oauth2.credentials import Credentials` and set `mock_flow.credentials = Credentials(token="...", refresh_token="...")` in test setup. This is more brittle to library internals but correctly exercises the auth path.

- **`busy_slots_service` now owns `service_client` — patch it there, not in `app.routers.busy_slots`.**
  After the modularization that moved business logic into service files, `service_client` is imported in `app.services.busy_slots_service`, not in the router. Tests that patched `app.routers.busy_slots.service_client` stopped intercepting anything and caused real DB hits. Correct patch path: `@patch("app.services.busy_slots_service.service_client")`. Apply the same principle whenever a router is refactored to delegate to a service — always trace where `service_client` is imported, not where it is called.

- **`get_event_busy_slots` chain depth changed after modularization — mock `.maybe_single()` not `.single()`.**
  After the router-to-service migration, `fetch_event_by_uid` uses `.select('*').eq('uid', uid).maybe_single().execute()`. Tests that mocked `.single.return_value` for the events table stopped returning data. Update all `busy_slots`-related test mocks to use `.maybe_single.return_value`. Similarly, the `event_participants` authorization check now uses `.eq().eq().in_().maybe_single()` and the participant list uses `.eq().neq().execute()` — two separate call chains that need separate mock branches.

- **Force-refresh proposals must be coordinator-only — always check authorization before running a heavyweight operation.**
  The initial `POST /events/{uid}/proposals` implementation allowed any authenticated participant to trigger a force-refresh (full re-generation). This was corrected to check `event['coordinator_id'] != current_user.id` and raise 403 for non-coordinators. The lazy view path (read cached proposals) remains available to all participants.

### Frontend

- **Merge all Supabase postgres_changes for an event into a single channel — do not create one channel per table.**
  The original `useEventSubscriptions` created a separate `supabase.channel(...)` for each table (`busy_slots`, `event_participants`, etc.). Supabase counts each channel toward connection limits. The consolidated pattern: one channel `event-subs-${uid}` with multiple `.on('postgres_changes', ...)` calls chained before `.subscribe()`. Use `refetchQueries` (not `invalidateQueries`) for real-time handlers so stale data is replaced immediately, not just marked dirty.

- **Query key inconsistency between `['event', uid]` and `['events', uid]` breaks cross-hook invalidation.**
  `useFinalize`, `useProposalFreshness`, `proposalUtils`, and `EventDetailClient` all had subtly different query keys for the same event data. After the subscription consolidation, the canonical key is `['events', uid]` (plural). Any hook that invalidates or reads the event query must use the same key. Grep `queryKey.*event` before adding a new hook that touches event data.

- **`EMPTY_PREFERRED_SLOTS` must be a module-level constant — do not inline `[]` as a default prop or fallback.**
  `EventDetailClient` passed `preferredSlots ?? []` to child components. Each render creates a new `[]` reference, which triggers a `useEffect` dependency change on every render, causing an infinite re-render loop. Fix: declare `const EMPTY_PREFERRED_SLOTS: PreferredSlot[] = []` once at module level and use it as the fallback. Same applies to any array or object used as a stable reference in dependency arrays.

- **Replace `useState(initialEvent)` with `useEvent(uid)` so event data stays live after edits.**
  The original `EventDetailClient` kept a local `useState(initialEvent)` that was seeded from SSR props and updated by the edit modal. After any other real-time change (e.g. finalization), the local state was stale. The fix: remove the local state, call `useEvent(uid)` (TanStack Query), and let the subscription invalidation keep it fresh. The edit modal's `onSuccess` now just invalidates `['events', uid]` instead of merging into local state.

- **The `write-calendar` toggle must be disabled when `source.is_write_calendar` is true.**
  Disabling a calendar source that is the current write calendar would orphan the write-calendar assignment, causing silent sync failures. Add `disabled={source.is_write_calendar}` to the enable/disable checkbox and add `cursor-not-allowed opacity-50` to the label with a tooltip: `"This is your write calendar. Select another write calendar before disabling."` The UX contract: a user must first assign a different write calendar, which automatically clears this one.

- **After navigating away from a deleted event, always call `router.refresh()` before `router.push()`.**
  This was documented in the Bug Fixes section above, but a regression re-appeared here. The `event_deleted` notification handler in `NotificationList` must use the same pattern: `router.refresh(); router.push('/dashboard')`. Without `router.refresh()`, the RSC cache still has the deleted event and it reappears on the dashboard until the user hard-reloads.

- **Supabase real-time `anon` policies are required for `postgres_changes` to fire in the browser.**
  The JS client subscribes without a signed-in Supabase session (auth is JWT-based via the backend). Without explicit `anon SELECT` policies on each real-time table, Supabase silently drops change events. Add `REPLICA IDENTITY FULL` on each table, add the table to the `supabase_realtime` publication, and add `create policy ... for select using (true)` for the `anon` role. Without `REPLICA IDENTITY FULL`, DELETE events carry no old row data and the payload is empty.

### Schema

- **`proposed_time_notes` RLS select policy must join through `proposed_times` to reach `event_participants`.**
  The `proposed_time_notes` table has no direct `event_id` column — it links only to `proposed_times(id)`. The select policy cannot simply check `ep.event_id = proposed_time_notes.event_id`. It must join: `proposed_times pt ON pt.id = proposed_time_notes.proposed_time_id` then `event_participants ep ON ep.event_id = pt.event_id WHERE ep.user_id = auth.uid()`. Any RLS policy on a table that is two hops from `event_participants` requires this explicit join chain — there is no shortcut.

### UI Component — `ProposedTimeOverlay`

- **Proposal overlays are positioned absolutely over the grid using `colIndex * (100% / 7)` — not relative to individual column divs.**
  `ProposedTimeOverlay` renders a flat list of absolutely positioned `<div>`s over the entire grid container. It does not render inside individual column `<div>`s. The column is encoded via `data-col={colIndex}` for debugging. The `left` style uses `calc(${colIndex} * (100% / 7))` and `width: calc(100% / 7)` to align with the grid's 7-column layout. This means the grid container must be `position: relative` and have a known width for the overlay to align correctly.

- **Use `isScrollable` to branch between `px`-based and `%`-based top/height geometry.**
  When the grid uses fixed `h-8` (32 px) rows (`isScrollable: true`), slot positions must be computed in pixels: `startRow * ROW_HEIGHT_PX + 2` and `rowsSpanned * ROW_HEIGHT_PX - 4`. When the grid uses percentage-based rows, use `calc(${(startRow / totalRows) * 100}% + 2px)`. Mixing px and % on the same grid causes visual misalignment. Pass `isScrollable` and `totalRows` as explicit props rather than inferring them from the grid's CSS.

### Backend — HTTP

- **Supabase `service_client` HTTP/2 connection sharing causes burst 500s under concurrent requests.**
  A single `service_client` instance (created at module load time) maintains one HTTP/2 connection pool. When multiple concurrent requests arrive simultaneously (e.g. the event detail page polling several endpoints at once), they share the same HTTP/2 connection. If that connection goes idle or hits a server-side timeout, Supabase drops it mid-stream (`RemoteProtocolError: Server disconnected`) and every in-flight request on that connection fails together. The symptom is a burst of identical 500s (e.g. 5 `proposed_time_notes` requests all failing at once), followed by full recovery on the next attempt.
  **Fix:** configure the Supabase client to use HTTP/1.1 (disabling connection multiplexing) or set a short keepalive timeout so stale connections are recycled before Supabase drops them:
  ```python
  import httpx
  from supabase import create_client

  # Force HTTP/1.1 to avoid shared-connection cascade failures
  http_client = httpx.Client(transport=httpx.HTTPTransport(http2=False))
  service_client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY, options={"http_client": http_client})
  ```

---

## Proposed Time Notes & Proposed Times

### Schema

- **`proposed_time_notes.event_uid` is a denormalized column added solely to enable Supabase real-time filtering.**
  Supabase real-time `filter` expressions cannot span joins — they match on columns that exist directly on the changed row. `proposed_time_notes` has no `event_id` column (it links to `proposed_times.id`). Without `event_uid`, the JS client would receive INSERT events for every note across every event and would have to discard them client-side. Adding `event_uid text not null` to the table allows the filter `event_uid=eq.${uid}` in `useEventSubscriptions`. This column is written by `proposal_notes_service.create_note` and indexed for the real-time query.

- **`proposed_time_notes` RLS select policy requires a two-hop join through `proposed_times` to reach `event_participants`.**
  The table has no direct `event_id` — it only has `proposed_time_id`. The authenticated-user select policy must join: `proposed_times pt ON pt.id = proposed_time_notes.proposed_time_id` then `event_participants ep ON ep.event_id = pt.event_id WHERE ep.user_id = auth.uid()`. The `anon` realtime policy uses the denormalized `event_uid` column instead to avoid the join entirely. Any RLS policy on a table that is two hops from `event_participants` requires this explicit join chain.

- **Two separate RLS select policies exist on `proposed_time_notes` for different consumers.**
  `proposed_time_notes_select` (authenticated users): two-hop join through `proposed_times → event_participants`. `proposed_time_notes_realtime_select` (anon role): single join `event_participants ep JOIN events e ON e.id = ep.event_id WHERE e.uid = proposed_time_notes.event_uid`. Both are required — the authenticated policy covers normal reads, the anon policy covers the Supabase real-time subscription which runs as the `anon` role.

### Backend

- **`proposal_notes_service.py` uses `service_client` for all reads and writes even though users only write their own notes.**
  `proposed_time_notes.user_id` references `auth.users(id)`, not `profiles(id)`. The `anon_client` (user-scoped) cannot compare `auth.uid()` to a column referencing `auth.users` when using the Python client. All DB access goes through `service_client`; ownership is enforced at the Python level: `delete_note` filters with `.eq("user_id", user_id)` and raises 404 if no row is deleted.

- **`_check_proposed_time_belongs_to_event` uses `service_client` in the router, not in a service function.**
  This is a narrow exception to the "service_client only in services" rule. The path-parameter ownership check (does `proposed_time_id` belong to `event.id`?) is router-level authorization, not business logic. It calls `service_client` directly in the router helper because `proposed_times` RLS requires a join that `anon_client` cannot satisfy. Keep this helper in the router file and do not promote it to a service function.

- **`proposal_notes` router uses `get_event_and_check_access` from `proposal_service` for event lookup and participant auth.**
  Rather than duplicating the event-fetch-and-participant-check logic, the notes router imports `get_event_and_check_access(uid, user_id)` from `proposal_service`. This function raises 404 if the event does not exist and 403 if the user is not a coordinator or participant. Reuse this pattern in any new router that needs per-event access control.

### Frontend

- **`proposalNotes` query key is scoped to `proposedTimeId`, not `eventUid`.**
  Each proposed time has its own note list. The query key `['proposalNotes', proposedTimeId]` allows granular invalidation — when a new note arrives via real-time, only the query for the specific proposed time is refetched. The real-time handler reads `payload.new.proposed_time_id` to determine which key to refetch. Scoping to `eventUid` would force all note queries to be invalidated whenever any note is added, even for unrelated proposals.

- **The `proposed_time_notes` subscription is a separate `supabase.channel()` from the main event subscriptions.**
  The main event channel (`event-subs-${uid}`) consolidates preferred_slots, busy_slots, event_participants, and events under one channel, all filtering by `event.id` (UUID). The notes channel (`proposal-notes-subs-${uid}`) filters on `event_uid` (text) — a different column on a different table. These cannot share a channel since the filter expression targets different column names. Always use a separate channel when the filter key differs from the main event channel's filter key.

- **`ProposedTimeNote` interface does not include `event_uid` — that field is backend-only.**
  The `event_uid` column exists on the DB row but is not included in the `ProposedTimeNote` TypeScript interface or the `ProposedTimeNoteResponse` Pydantic model. It is an implementation detail of the real-time subscription infrastructure. Callers never need to read it back, so it is intentionally omitted from the API response.

- **`ProposedTime` in `types/index.ts` uses `conflicts: number`, matching the DB column name — not `conflict_count`.**
  The DB column is `conflicts`. The API's `ProposalResponse` Pydantic model exposes it as `conflict_count` (the modularization renamed it for clarity). The frontend `ProposedTime` interface uses `conflicts` (matching the raw DB shape), while test fixtures that reference `ProposalResponse` use `conflict_count`. These are two different type shapes — do not conflate them.

---

## Production Deploy & Post-Launch Fixes

Lessons surfaced during the late-April 2026 production-stabilisation push (Docker rollout, calendar reauth flow, dedup hardening, finalize idempotency).

### Backend — Calendar credential refresh

- **Persist and re-hydrate `credentials.expiry`, otherwise `googleapiclient` never refreshes.**
  `credentials_from_dict` must populate `Credentials(..., expiry=_parse_expiry(creds_data.get("expiry")))`. Without it, `credentials.expired` is permanently `False`, googleapiclient skips the refresh attempt, a revoked refresh token never raises `RefreshError`, and `needs_reauth` never trips — the user silently sees stale availability. The expiry must also be persisted on the initial OAuth connect (`credentials.expiry.isoformat()` into `calendar_accounts.credentials`) so the very first sync has the same refresh-detection behaviour as subsequent syncs. The Google library compares expiry against `datetime.utcnow()` (naive UTC), so any tz-aware stored value must be normalised to naive UTC in `_parse_expiry` before being passed to `Credentials`.

- **Catch `google.auth.exceptions.RefreshError` in both `sync_service` and `finalize_service`.**
  When the refresh token is revoked or expired, googleapiclient raises `RefreshError` mid-call. `sync_service._sync_user` must catch it, call `mark_account_needs_reauth(account_id)`, and continue to the next account so other calendars still sync. `finalize_service.finalize_event` must catch it, mark the account, and raise `HTTPException(422, detail="calendar_credentials_expired")` — the frontend distinguishes this from `no_write_calendar` to show a "Reconnect" prompt instead of "Pick a write calendar".

- **Auto-sync busy slots inside the OAuth callback after persisting the row.**
  `calendar_accounts.google_calendar_callback` calls `sync_service.sync_busy_slots(state)` after `connect_google_account` succeeds. Wrap it in `try/except` and log-and-continue — the connect flow must not fail on a downstream sync hiccup. Users land on Settings with availability already populated and `last_synced_at` set, which removes the "did the connect actually work?" doubt loop.

### Backend — Notifications & invitations dedup

- **`_process_pending_invitations` must filter `is_("invitee_id", "null")` for re-login idempotency.**
  Without this filter, every login re-creates an `event_invitation` notification for every still-pending invite belonging to the user's email, because the function looks up invites by email and the email match alone doesn't change between logins. After the first run, `invitee_id` is populated and the row is excluded from the query, making the function safely idempotent across re-logins until the invitation transitions out of `pending`.

- **A partial unique index blocks duplicate pending invitation notifications at the DB layer.**
  The application-level idempotency above is the primary defence, but a partial unique index `notifications_unique_pending_invitation ON (user_id, event_id) WHERE notification_type = 'event_invitation' AND action_taken = false` is the safety net. The `WHERE action_taken = false` clause is critical — without it, a user who declined an invite could never receive a fresh one for the same event. With it, only the *pending* slot is unique-constrained.

### Backend — Finalize idempotency

- **`finalize_event` must early-return 409 when `event['status'] == 'confirmed'`.**
  Without the guard, double-clicking the finalize button creates a second Google Calendar event, sends duplicate "event confirmed" notifications, and overwrites `finalized_*_utc` fields. The check must run *before* the GCal write — checking only at the DB-update step is too late, the GCal side-effect already fired.

### Backend — HTTP / supabase client

- **Forcing HTTP/1.1 on the postgrest client must preserve `base_url`, `headers`, and `timeout`.**
  The HTTP/2 cascade-500 workaround (rebuilding the inner `httpx.Client` with `http2=False`) silently breaks every request if the new client is constructed without the original `base_url` (request goes to `httpbin.org`-equivalent — i.e., nowhere), `headers` (missing `apikey` and `Authorization` → 401 on every call), or `timeout` (default of 5s causes spurious read timeouts on slower endpoints). Read the originals off the auto-built session and pass them through.

### Frontend — API error handling

- **`lib/api.ts` must attach `.detail` (and any structured fields) onto thrown `Error` objects.**
  Backend returns `{ "detail": "calendar_credentials_expired" }` on 422. Consumers like `FinalizeCard` branch on `err.detail === 'calendar_credentials_expired'` to show a reconnect button. Plain `throw new Error(message)` strips the structured payload — the consumer's `if (err.detail === ...)` branch never fires and the user sees a generic toast. Mutate the Error before throwing: `const err = new Error(detail); (err as any).detail = detail; throw err`.

- **The 401 handler must clear both `localStorage` and the `token` cookie via `clearAuth()`.**
  Clearing only `localStorage` leaves the cookie behind; the middleware reads the cookie on the next navigation, decides the user is authorised, and routes them back into the app — where `lib/api.ts` immediately 401s again because the bearer token in `localStorage` is gone. The user is stuck in a redirect loop. `useAuthStore.getState().clearAuth()` wipes both and triggers the realtime client to drop its `accessToken` callback's now-empty token.

### Frontend — Realtime notifications

- **The `notifications` realtime INSERT handler must NOT call `notificationStore.increment()`.**
  Refetch the unread count from the server instead. Under React StrictMode the effect's setup runs twice in development; an optimistic `increment()` double-counts and the badge drifts off the server-truth value until the next manual refetch. A single `queryClient.invalidateQueries({ queryKey: ['notifications', 'unread-count'] })` is authoritative and StrictMode-safe.

### Frontend — Reconnect UX

- **The navbar reauth pill always routes to `/settings`, never to a deep link.**
  The pill is a global "you have an account that needs attention" signal. Deep-linking to `/settings#account-${id}` is fragile when the user has multiple connected accounts and one of them just got disconnected — the anchor target may not exist on first render. `/settings` is stable; the per-account "Reconnect" button on that page handles the specific account.

- **Invalidate `['calendar-accounts']` after a successful sync.**
  `last_synced_at` and `needs_reauth` are read off the calendar-accounts cache. Without invalidation after a `useSyncMyCalendar` mutation, the Settings page still shows the pre-sync `last_synced_at`, the user assumes the sync silently failed, and they click again.

### Docker / Next.js standalone output

- **Pages that read fresh request-time data need `export const dynamic = 'force-dynamic'`.**
  Auth callback (`/auth/callback`), `/settings` (reads `?connect_calendar=true`), and `/events/new` (reads server cookies) must opt out of static generation. In Next.js standalone-output mode they're prerendered at build time by default; the query string and cookies are then permanently empty in the deployed bundle.

- **`NEXT_PUBLIC_*` env vars are inlined at build time, not runtime.**
  Setting them in docker-compose's `environment:` block has no effect on the Next.js bundle — they need to be passed as `--build-arg` to the frontend Dockerfile, with corresponding `ARG` and `ENV` lines. In docker-compose this is `args:` under `build:`. Symptom of getting it wrong: the deployed app has `undefined` for `NEXT_PUBLIC_SUPABASE_URL` and the realtime client crashes at module load.

- **The frontend `/api/*` proxy target must be derived from a server-side env var.**
  Hardcoding `http://localhost:8000` in `next.config.js` rewrites works in local dev and breaks in docker-compose (where the backend is reachable as `http://backend:8000`). Read it off `process.env.API_URL` (a server-only var, no `NEXT_PUBLIC_` prefix) so the proxy target can be swapped per environment without rebuilding.

### Schema

- **`schema.sql` is now a `pg_dump` snapshot, not hand-written DDL.**
  Editing it directly is a footgun — the next regeneration will overwrite the edit. Schema changes belong in Supabase migrations (`supabase/migrations/`) and the snapshot is regenerated from the live DB afterwards.

## Hydration Mismatches & TZ-Dependent SSR Rendering

Lessons surfaced while fixing React errors `#418` ("hydration failed") and `#423` ("recovered by client-rendering the entire root") that appeared on the event detail page first and the dashboard immediately after.

### Frontend — SSR rendering of locale/TZ-dependent strings

- **Any component that renders `toLocaleDateString` / `toLocaleTimeString` from inside an SSR'd tree will mismatch on hydration.**
  `lib/dates.ts` helpers (`formatDateWindow`, `formatTime`, `formatLongDate`, etc.) all funnel into `toLocaleDateString('en-US', ...)`. The server runs in UTC; the client runs in the user's local timezone. Identical input UTC timestamps produce different formatted strings — e.g. a Jun 14 23:00 UTC stamp shows as "Jun 14" on the server and "Jun 15" in any +01:00 or later timezone. React detects the divergence on hydrate, throws away the SSR'd HTML, and re-renders the entire root client-side. The user sees a flash and console errors; you lose the SSR perf benefit anyway.

- **The fix: SSR a TZ-neutral skeleton; let the client render the real data after hydrate.**
  Pattern: convert the page file to a *thin* server component that only does request-time things (cookies, redirects) and renders a sibling client component. The client component uses TanStack Query (`useEvent`, `useEvents`, etc.) and branches: `isLoading || !data → <Skeleton />` and `data → <Loaded data={data} />`. The server emits the skeleton (no dates, no `toLocale*`); the client hydrates the same skeleton (matches exactly); then the query resolves and the real UI renders only in the browser, with the user's actual timezone. Applied to `app/events/[uid]/page.tsx` first, then `app/dashboard/page.tsx`.

- **`page.tsx` after the fix should contain almost nothing — just the auth check.**
  ```tsx
  // app/dashboard/page.tsx
  export default async function DashboardPage() {
    const cookieStore = await cookies()
    const token = cookieStore.get('token')?.value
    if (!token) redirect('/')
    return <DashboardClient />
  }
  ```
  No data fetching, no `<EventCard>`, no date helpers. If you find yourself adding a `fetchX` import here, you're re-introducing the SSR rendering path that caused the bug.

- **Delete the corresponding `fetchers.ts` after the migration.**
  When `app/<route>/page.tsx` stops fetching, the per-route `fetchers.ts` becomes dead code. Leaving it around invites future server components to import it again. After the dashboard fix, `app/dashboard/fetchers.ts` was removed. Verify with `grep -rln "fetchEvents\|fetchCalendarAccounts" frontend/` before deleting.

- **Tests for the page need to mock the hooks, not the fetchers.**
  Pre-fix, `EmptyStates.test.tsx` mocked `fetchEvents`/`fetchCalendarAccounts` and called `await DashboardPage()` to exercise the SSR render. Post-fix, `DashboardPage()` returns `<DashboardClient />`, so the test must `vi.mock('@/hooks/useEvent', () => ({ useEvents: vi.fn() }))` and set `vi.mocked(useEvents).mockReturnValue({ data: [...], isLoading: false })`. The `await DashboardPage()` call still works because the page is async, but the assertions now run against the client component's render of the mocked hook data.

### Backend — JWT claims required by Supabase services

- **The JWT signed in `_create_jwt` must include `"role": "authenticated"`.**
  Without this claim, PostgREST falls back to the default `anon` role and `TO authenticated` RLS policies don't apply; Supabase Realtime's `postgres_changes` rejects the channel join entirely (channel sits in `joining` state forever, no error message visible to the user). The conftest's integration-test JWT had this claim from day one — production was missing it, which is why the realtime breakage only surfaced once `realtime.messages` policies were tightened from `TO anon` to `TO authenticated` and unmasked the latent missing-role bug. Symptom in the browser console: `supabase.realtime.channels.forEach(c => console.log(c.topic, c.state))` shows every channel as `joining` despite `connectionState() === 'open'`.

### Frontend — Supabase Realtime authentication

- **Use `createClient(url, key, { realtime: { accessToken: () => Promise<string|null> } })`, not `setAuth(token)` after-the-fact.**
  In supabase-js v2.101+ `setAuth` is `async` and returns a `Promise<void>`. Calling it without `await` is fire-and-forget; React continues rendering, dashboard components mount, channels call `.subscribe()` with whatever auth the client currently has — which is the bare anon key. The `phx_join` frame goes out unauthenticated and the Realtime server holds it in limbo. The `accessToken` callback option is invoked on-demand by the realtime client at connect time, on every channel join, and after `setAuth()` is called with no args — eliminating the race entirely. The auth store calls `supabase.realtime.setAuth()` (no args) on `setUser` / `clearAuth` to trigger a re-auth of any open channels using the now-updated callback.

### Database — Cascade triggers under `supabase_auth_admin` role

- **Triggers without `SECURITY DEFINER` will fail when fired by `auth.admin.delete_user`.**
  Cascades from `auth.users` → `profiles` → `event_participants` (etc.) execute under the `supabase_auth_admin` role, not `service_role`. Triggers that aren't `SECURITY DEFINER` inherit that role's RLS context. After tightening `realtime.messages` to `TO authenticated`, broadcast triggers like `broadcast_event_changes`, `broadcast_participant_changes`, `broadcast_preferred_slots_changes`, `broadcast_notification_changes` (none of which are `SECURITY DEFINER`) silently fail to write to `realtime.messages` from inside `delete_user`'s cascade — the auth API returns the unhelpful `Database error deleting user`. Fix: in `account_service.delete_account`, **explicitly** purge user-owned rows under `service_role` (which has BYPASSRLS) before calling `auth.admin.delete_user`. The remaining cascade then has nothing to UPDATE/DELETE for those tables, so no triggers fire under the failing role context. Tables that *do* have `SECURITY DEFINER` broadcast triggers (`busy_slots`, `event_participants_broadcast_trigger`, `notifications_broadcast_trigger`, `proposed_time_notes_broadcast_trigger`) are fine to let the cascade clean up.

### Docker — Build cache fooling `--no-cache` rebuilds

- **`docker compose down && docker compose up` does NOT rebuild the image.**
  It just restarts the existing container with the same image. To pick up code changes you need an explicit `docker compose build --no-cache <service>` before `up`, OR use `docker compose up --build`. Verify the rebuild actually happened with `docker compose images <service>` — the `CREATED` column should read seconds-ago, not hours-ago. When troubleshooting "I changed the file but the container doesn't see it," this is almost always the cause; the second-most-likely is a stale browser bundle (open DevTools → Network → tick "Disable cache" → reload).

### Frontend — Overlay DOM order

- **`overlayContent` must be rendered AFTER the grid `<div>` in `AvailabilityGrid`, not before it.**
  In `frontend/components/event/AvailabilityGrid.tsx`, the overlay container is a sibling of the grid div, both inside a `position: relative` parent. DOM order determines stacking context for `position: absolute` siblings — a later sibling naturally paints on top. When `{overlayContent}` was placed before `<div className="grid ...">`, the grid cells were rendered after the overlay and covered it. Moving `{overlayContent}` to after the grid div makes it stack on top without needing any `z-index`. Apply this rule anywhere an overlay must render above a sibling: place it after the sibling in the JSX, not before.
