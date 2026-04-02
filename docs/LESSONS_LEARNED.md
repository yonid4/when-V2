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

- **`_process_pending_invitations` creates an `invite_accepted` notification for the inviter, not an `event_invitation` notification for the new user.**
  The data model documentation describes an `event_invitation` notification being created for the invitee on signup. The actual implementation creates an `invite_accepted` notification for the *inviter* instead. The invitee sees the event via their `event_participants` row, not via a notification. Tests must accept `invite_accepted` as the notification type.

- **Pending invitation matching updates `status` to `"accepted"` (not setting `invitee_id`).**
  The implementation updates the invitation's `status` to `"accepted"` via `update()` rather than setting `invitee_id`. The `invitee_id` is implicitly resolved through the new `event_participants` row. Tests should verify `status == "accepted"` rather than looking for an `invitee_id` update.

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
