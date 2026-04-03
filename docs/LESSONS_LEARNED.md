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
