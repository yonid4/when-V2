# TESTS.md — When. v2 Test Documentation

This file is the canonical record of all tests written across sprints. It is updated at the end of each sprint after tests pass.

---

## Structure

Each sprint section contains:
- **Files written** — test file paths
- **Coverage** — what each test covers
- **Mock patterns** — key mocking strategies used
- **Gotchas** — failures, surprises, or lessons specific to the tests

---

## Sprint 1 — Auth

**Completed:** 2026-04-01
**Result:** 11/11 backend tests, 16/16 frontend tests passing

### Files Written

| File | Domain | Tests |
|------|--------|-------|
| `backend/tests/test_auth.py` | Auth router, auth service, get_current_user dependency | 11 |
| `frontend/__tests__/auth/CallbackPage.test.tsx` | Auth callback page | 3 |
| `frontend/__tests__/auth/api.test.ts` | lib/api fetch wrapper | 3 |
| `frontend/__tests__/auth/authStore.test.ts` | Zustand authStore | 5 |
| `frontend/__tests__/auth/middleware.test.ts` | Next.js middleware | 5 |

### Coverage

#### Backend

**test_auth.py** (11 tests)
- `GET /auth/google` — returns 307 redirect to Google OAuth with `client_id`, `redirect_uri`, `scope` params
- `GET /auth/me` with valid JWT — returns correct user id and email (200)
- `GET /auth/me` with no Authorization header — returns 403 (HTTPBearer behavior)
- `GET /auth/me` with malformed JWT — returns 401
- `GET /auth/me` with expired JWT — returns 401
- `GET /auth/me` with valid JWT but unknown user_id — returns 401
- `get_current_user` dependency with valid JWT — resolves user without error
- `get_current_user` dependency with no token — returns 403 (HTTPBearer)
- Callback flow creates profiles row with email_address, full_name, avatar_url
- Callback flow creates calendar_accounts row with provider=google and credentials; verifies `google_auth_token` (legacy column) is NOT written to profiles
- New user signup with pending invitation: sets invitee_id, creates event_invitation notification for invitee, leaves status=pending, does NOT create event_participants row
- `_create_jwt` produces token with `sub` (user_id) and `email` claims

#### Frontend

**CallbackPage.test.tsx** (3 tests)
- Stores token in localStorage, calls `setUser`, redirects to `/dashboard` when token param is present
- Redirects to `/` when no token param
- Redirects to `/` when API call fails

**api.test.ts** (3 tests)
- Attaches `Authorization: Bearer <token>` header when token exists in localStorage
- Sends no Authorization header when no token in localStorage
- Clears token from localStorage and sets `window.location.href='/'` on 401 response

**authStore.test.ts** (5 tests)
- Initial state has `user: null`, `token: null`
- `setUser()` sets user and token in store
- `clearAuth()` resets state to initial null values
- Token persists in localStorage after `setUser()`
- Token is cleared from localStorage after `clearAuth()`

**middleware.test.ts** (5 tests)
- Redirects to `/` (307) when accessing a protected route with no token
- Passes through (200) with a valid token on a protected route
- Passes through on `/` with no token (public path)
- Passes through on `/auth/callback` with no token (public path)
- Passes through on `/` with a valid token — middleware does NOT redirect `/` to `/dashboard`

### Mock Patterns

#### Backend — patching service_client on the dependencies module
```python
# get_current_user reads from app.dependencies.service_client, NOT from auth_service
@patch("app.dependencies.service_client")
def test_auth_me_success(mock_svc):
    profile = _make_profile_row()
    mock_svc.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value = MagicMock(data=profile)
    with patch("app.services.auth_service.service_client") as mock_auth_svc:
        ...
```

#### Backend — per-table side_effect for complex callback flows
```python
# test_pending_invitations_matched_on_signup routes each table to its own mock
# to capture insert/update calls without chains colliding
def make_table(table_name):
    tbl = MagicMock()
    if table_name == "event_invitations":
        tbl.select.return_value.eq.return_value.eq.return_value.execute.return_value = MagicMock(data=[pending_invite])
        def capture_update(data):
            invitations_updated.append(data)
            chain = MagicMock()
            chain.eq.return_value.execute.return_value = MagicMock(data=[])
            return chain
        tbl.update.side_effect = capture_update
    ...
mock_svc.table.side_effect = make_table
```

#### Frontend — mutable closure for useSearchParams
```typescript
// mockToken declared at module scope and mutated per test
let mockToken: string | null = null

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: mockReplace }),
  useSearchParams: () => ({
    get: (key: string) => (key === 'token' ? mockToken : null),
  }),
}))
```

#### Frontend — Zustand reset between tests
```typescript
// Re-importing does NOT reset Zustand state — must use setState directly
beforeEach(() => {
  act(() => {
    useAuthStore.setState({ user: null, token: null })
  })
})
```

#### Frontend — dynamic import of lib/api to isolate localStorage state
```typescript
// api.ts reads localStorage at call time, not module-load time.
// Dynamic import avoids module cache from carrying token state between tests.
it('attaches Authorization header when a token exists', async () => {
  localStorage.setItem('token', 'my-jwt-token')
  vi.stubGlobal('fetch', mockFetch)
  const { api } = await import('@/lib/api')
  await api.get('/events')
  ...
})
```

### Gotchas

- **`RedirectResponse` returns 307 by default, not 302.** FastAPI's `RedirectResponse` defaults to HTTP 307. Tests must accept `in (302, 307)`.
- **`HTTPBearer` returns 403 (not 401) when Authorization header is absent.** Only returns 401 when a malformed/expired token is actually supplied. Tests for "missing token" must assert 403.
- **`get_current_user` returns 401 (not 404) for unknown user.** When a valid JWT decodes but user_id is absent from profiles, the dependency raises 401.
- **JWT claims use `sub` for user_id.** The `get_current_user` dependency reads `payload.get("sub")`, not `payload.get("user_id")`.
- **`_process_pending_invitations` does NOT add invitee to event_participants.** It sets `invitee_id` on the invitation and creates a notification. The participant row is only created when the user explicitly accepts via `PUT /api/invitations/{id}/respond`.
- **`_upsert_profile` does NOT write `google_auth_token`.** Credentials live only in `calendar_accounts.credentials`. The legacy `google_auth_token` column is never touched in v2.
- **`npm run test` script was missing from `package.json`.** Had to add `"test": "vitest run"` and `"test:watch": "vitest"` manually.
- **Middleware does NOT redirect `/` to `/dashboard` when a token is present.** `/` is in `PUBLIC_PATHS` and always passes through. The redirect for logged-in users is the page component's responsibility.

---

## Sprint 2 — Events CRUD & Dashboard

**Completed:** 2026-04-01
**Result:** 10/10 backend tests, 12/12 frontend tests passing

### Files Written

| File | Domain | Tests |
|------|--------|-------|
| `backend/tests/test_events.py` | Event service (create, list, get, update, delete) | 10 |
| `frontend/__tests__/EventCard.test.tsx` | EventCard dashboard component | 7 |
| `frontend/__tests__/CreateEventForm.test.tsx` | CreateEventForm multi-step page | 6 |

### Coverage

#### Backend

**test_events.py** (10 tests)
- `create_event` — generates 12-char UID, inserts event row, adds coordinator as participant with `rsvp_status='going'`, `status='accepted'`; returns EventResponse with participants
- `create_event` — coordinator participant row inserted with `rsvp_status='going'`, `user_id` matching coordinator, `status='accepted'`
- `get_events_for_user` — returns list of events where user is coordinator or participant
- `get_event_by_uid` — happy path: returns event with nested participant profiles
- `get_event_by_uid` → 404 when event does not exist (`.maybe_single()` returns None)
- `get_event_by_uid` → 403 when requester is not the coordinator and not in participants list
- `update_event` — happy path: updates name, returns updated EventResponse
- `update_event` — sets `proposals_needs_regeneration=True` in update payload when time window fields change
- `update_event` → 403 when requester is not the coordinator
- `delete_event` — sends `event_deleted` notifications to all non-coordinator participants via `service_client`; verifies notification_type and user_id set for each

#### Frontend

**EventCard.test.tsx** (7 tests)
- Renders event name
- Renders `event_type` badge
- Renders status badge with correct text
- Links to event detail page using uid (`href=/events/{uid}`)
- Shows participant avatars with initials (first letter of `full_name`) when no `avatar_url`
- Shows overflow count `+N` when more than 4 participants
- Has hover lift CSS class (`group-hover:-translate-y-1`) on card element

**CreateEventForm.test.tsx** (6 tests)
- Renders step 1 with event name input and type cards (Meeting, Social, Birthday, Other)
- Shows step indicator with Details, Availability, Confirm labels
- Shows validation error "Event name is required" when submitting step 1 without a name
- Advances to step 2 after filling event name ("Find the perfect window" heading appears)
- Renders duration segmented selector on step 2 (30 min, 1 hr, 1.5 hr, 2 hr)
- Shows "Back to Dashboard" link with `href=/dashboard` on step 1

### Mock Patterns

#### Backend — `_make_chain()` helper for reusable fluent mock
```python
def _make_chain():
    """Create a fresh chainable mock (every builder method returns itself)."""
    chain = MagicMock()
    for m in ("eq", "neq", "in_", "single", "maybe_single"):
        getattr(chain, m).return_value = chain
    return chain

def _mock_db():
    """Return a mock Supabase client with per-operation chains per table."""
    db = MagicMock()
    tables = {}

    def _get_table(table_name):
        if table_name not in tables:
            table = MagicMock()
            for op in ("select", "insert", "update", "delete"):
                chain = _make_chain()
                getattr(table, op).return_value = chain
            tables[table_name] = table
        return tables[table_name]

    db.table = MagicMock(side_effect=_get_table)
    return db
```

#### Backend — separate `service_client` patch for delete notifications
```python
# delete_event uses service_client (bypasses RLS) for notifications
# and get_authed_client for querying/deleting the event itself
@patch("app.services.event_service.service_client")
@patch("app.services.event_service.get_authed_client")
def test_delete_event_notifies_participants(mock_get_client, mock_svc):
    ...
    notif_table = MagicMock()
    notif_table.insert.return_value.execute.return_value = MagicMock(data=[])
    mock_svc.table.return_value = notif_table
    ...
    notif_insert_data = notif_table.insert.call_args[0][0]
    assert len(notif_insert_data) == 2
```

#### Frontend — `QueryClientProvider` wrapper for mutation hooks
```typescript
function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  )
}
```

#### Frontend — mocking `next/link` as a plain anchor
```typescript
vi.mock('next/link', () => ({
  default: ({ href, children, ...props }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...props}>{children}</a>
  ),
}))
```

### Gotchas

- **`get_event_by_uid` uses `.maybe_single()` not `.single()`.** `.single()` throws on empty results; `.maybe_single()` returns None. All test mocks must use `.maybe_single.return_value` and `_make_chain()` must include `"maybe_single"` in its chained method list.
- **`_mock_db()` gives each operation (select/insert/update/delete) its own chain per table.** Without this, `select().eq().execute()` and `update().eq().execute()` on the same table mock overwrite each other's `.return_value`. The per-operation chain isolation is the key structural pattern for event service tests.
- **`delete_event` uses both `get_authed_client` (for querying/deleting the event) and `service_client` (for inserting notifications).** Both must be patched separately. Using `mock_svc.table.return_value` for the notification table is safe because `service_client` is only called once in that function.

---

## Sprint 3 — Participants, Invitations, Notifications

**Completed:** 2026-04-02
**Result:** 44/44 backend tests, 58/58 frontend tests passing

### Files Written

| File | Domain | Tests |
|------|--------|-------|
| `backend/tests/test_participants.py` | Participants router/service | 9 |
| `backend/tests/test_invitations.py` | Invitations router/service | 7 |
| `backend/tests/test_notifications.py` | Notifications router/service | 6 |
| `frontend/__tests__/sprint3/ParticipantList.test.tsx` | ParticipantList component | 6 |
| `frontend/__tests__/sprint3/InviteInput.test.tsx` | InviteInput component | 6 |
| `frontend/__tests__/sprint3/RsvpSelector.test.tsx` | RsvpSelector component | 5 |
| `frontend/__tests__/sprint3/NotificationList.test.tsx` | NotificationList component | 7 |
| `frontend/__tests__/sprint3/NotificationBell.test.tsx` | NotificationBell + unread badge | 5 |

### Coverage

#### Backend

**test_participants.py** (9 tests)
- `GET /api/events/{uid}/participants` — returns participant list with profile data
- `GET /api/events/{uid}/participants` → 403 when requester is not a member
- `PUT /api/events/{uid}/participants/{user_id}/rsvp` — user updates own RSVP status
- `PUT /api/events/{uid}/participants/{user_id}/rsvp` → 403 when updating another user's RSVP
- `PUT /api/events/{uid}/participants/{user_id}/permissions` → 403 for non-coordinator
- `DELETE /api/events/{uid}/participants/{user_id}` — self-removal
- `DELETE /api/events/{uid}/participants/{user_id}` → 403 when non-coordinator removes another user
- `GET /api/events/{uid}/participants` → 404 when event does not exist
- `PUT /api/events/{uid}/participants/{user_id}/permissions` → 200 for coordinator

**test_invitations.py** (7 tests)
- `POST /api/events/{uid}/invite` — invite existing user: creates invitation + notification → 201
- `POST /api/events/{uid}/invite` — invite email with no account: creates invitation with invitee_id=null → 201
- `POST /api/events/{uid}/invite` → 409 when invitee is already a participant
- `POST /api/events/{uid}/invite` → 403 when requester is not a participant or coordinator
- `PUT /api/invitations/{id}/respond` with `accept` → 204, adds to event_participants
- `PUT /api/invitations/{id}/respond` with `decline` → 204
- `PUT /api/invitations/{id}/respond` → 403 when invitation belongs to a different user

**test_notifications.py** (6 tests)
- `GET /api/notifications` → 200 with list of notifications for current user
- `GET /api/notifications` → 200 with empty list when user has no notifications
- `POST /api/notifications/{id}/read` → 200 with updated notification (is_read=true)
- `POST /api/notifications/{id}/read` → 403 when notification belongs to another user
- `POST /api/notifications/{id}/action` with `accept` → 200, calls respond_to_invitation internally
- `GET /api/notifications` → 403 when no auth token

#### Frontend

**ParticipantList.test.tsx** (6 tests)
- Shows loading state
- Shows empty state when no participants
- Renders participant full_name
- Shows COORDINATOR label for coordinator
- Shows remove button when current user is coordinator (for non-coordinator entries)
- Calls `removeParticipant` when Leave button clicked (self-removal)

**InviteInput.test.tsx** (6 tests)
- Renders invite form for coordinator
- Returns null when user has no invite permission (`can_invite=false`, not coordinator)
- Shows error for invalid email (non-email string)
- Shows error when email field is empty
- Calls `invite` mutation with email on valid submit
- Renders form for participant with `can_invite=true`

**RsvpSelector.test.tsx** (5 tests)
- Returns null for the coordinator (they have no RSVP to set)
- Returns null when current user is not a participant
- Renders Going / Maybe / Not Going buttons for a non-coordinator participant
- Calls `updateRsvp` with the correct payload when an option is clicked
- Applies active style to the button matching the current `rsvp_status`

**NotificationList.test.tsx** (7 tests)
- Shows loading state
- Shows empty state when notification list is empty
- Renders notification title and message
- Shows Accept / Decline buttons for unactioned `event_invitation` notifications
- Calls `takeAction` with `{ notificationId, action: 'accept' }` when Accept is clicked
- Calls `markRead` when a non-invitation unread notification is clicked
- Shows "Accepted" badge when `event_invitation` action_taken=true and action_type='accept'

**NotificationBell.test.tsx** (5 tests)
- Renders the bell icon button
- Does not show badge when unreadCount is 0
- Shows unread count badge when unreadCount > 0
- Shows "99+" when unreadCount exceeds 99
- Renders NotificationList inside popover content

### Mock Patterns

#### Backend — per-table routing on shared db mock
```python
# When a service queries two tables with identical chain depth,
# flat return_value assignment causes the last write to win.
# Fix: use side_effect to route by table name.
def make_db_table(table_name):
    tbl = MagicMock()
    if table_name == "notifications":
        tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=notif)
    elif table_name == "events":
        tbl.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(data=event_row)
    return tbl

db = MagicMock()
db.table.side_effect = make_db_table
```

#### Backend — patching multiple services in one test
```python
# test_take_action_accept patches 5 items:
# invitation_service.service_client, invitation_service.get_authed_client,
# notification_service.service_client, notification_service.get_authed_client,
# dependencies.service_client
@patch("app.services.invitation_service.service_client")
@patch("app.services.invitation_service.get_authed_client")
@patch("app.services.notification_service.service_client")
@patch("app.services.notification_service.get_authed_client")
@patch("app.dependencies.service_client")
def test_take_action_accept(mock_dep_svc, mock_notif_authed, mock_notif_svc, mock_inv_authed, mock_inv_svc):
    ...
```

#### Frontend — inline vi.fn() in mock factory to avoid hoisting errors
```typescript
// WRONG — const variables referenced before init
const mockRemoveChannel = vi.fn()
vi.mock('@/lib/supabase', () => ({
  supabase: { removeChannel: mockRemoveChannel }  // ReferenceError at runtime
}))

// CORRECT — inline vi.fn() inside the factory
vi.mock('@/lib/supabase', () => ({
  supabase: {
    channel: vi.fn(() => ({
      on: vi.fn().mockReturnThis(),
      subscribe: vi.fn(),
    })),
    removeChannel: vi.fn(),
  },
}))
```

#### Frontend — hook mocks with vi.mocked for per-test overrides
```typescript
vi.mock('@/hooks/useParticipants', () => ({
  useParticipants: vi.fn(),
  useUpdateRsvp: () => ({ mutate: mockUpdateRsvp, isPending: false }),
}))

import { useParticipants } from '@/hooks/useParticipants'

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useParticipants).mockReturnValue({ data: [] } as any)
})
```

### Gotchas

- **Coordinator bypass in `invite_by_email`**: the service originally required a participant row for ALL callers including the coordinator, causing a 403 for coordinator invites. Fixed by checking `is_coordinator` before querying `event_participants`.
- **`invitee_id` default in respond tests**: `_make_invitation_row()` must default `invitee_id` to the same value as the current test user (`"user-uuid-1"`), otherwise `respond_to_invitation` raises 403 ("This invitation is not for you").
- **`.maybe_single()` vs `.single()` in event_service**: The service uses `.maybe_single()` (returns None on empty) not `.single()` (raises on empty). All `test_events.py` mock chains must use `.maybe_single.return_value` and `_make_chain()` must include `"maybe_single"` in its list of chained methods.
- **`type="email"` blocks JSDOM form submission**: JSDOM's built-in email validation silently prevents `onSubmit` from firing for invalid email strings. Changed `InviteInput` to `type="text"` and kept the custom regex validation.
- **`@/components/ui/popover` must exist for Vite to transform `NotificationBell.tsx`**: The test mocks the module, but Vite still resolves the import at transform time. If the file is missing, the entire test suite fails with `Failed to resolve import`. Created a minimal hand-rolled implementation using React state.
- **`vi.mock` factory closure hoisting**: Variables declared with `const` at module scope are not yet initialized when `vi.mock` factories run (hoisted to top). Any reference to such variables inside the factory causes `ReferenceError: Cannot access 'x' before initialization`. Always use inline `vi.fn()` or `vi.hoisted()` for mock factory dependencies.

---

_Append new sprint sections below as sprints complete._
