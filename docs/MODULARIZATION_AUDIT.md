# MODULARIZATION_AUDIT.md — When. v2

**Date:** 2026-04-09  
**Branch:** sprint5  
**Audited against:** `docs/CLAUDE.md` architectural rules  
**Scope:** All files in `backend/app/{routers,services,models,utils,scheduler}/` and `frontend/{hooks,components,app,lib,stores}/`

---

## BACKEND

### Routers

#### `routers/proposals.py` — 123 lines
**CRITICAL VIOLATIONS:**
- Defines `ProposalResponse` Pydantic model inline (should be in `models/slot.py`)
- Helper `_get_event_and_check_access()` calls `service_client` directly — business logic + DB access in a router
- Helper `_get_cached_proposals()` calls `service_client` directly
- **Rule broken:** Routers must call services only; no Supabase in routers

#### `routers/preferred_slots.py` — 145 lines
**CRITICAL VIOLATIONS:**
- Defines `PreferredSlotCreate` and `PreferredSlotResponse` Pydantic models inline (should be in `models/slot.py`)
- Helper `_get_event_and_check_participant()` calls `service_client` directly
- All four CRUD route handlers call `service_client` directly — **no service layer exists for preferred_slots**
- **Rule broken:** Routers must call services only; no Supabase in routers

#### `routers/finalize.py` — 116 lines
**CRITICAL VIOLATIONS:**
- Defines `FinalizeRequest` and `FinalizeStatusResponse` Pydantic models inline (should be in `models/`)
- Helper `_get_event_by_uid()` calls `service_client` directly
- GET `/status/{uid}` endpoint body calls `service_client` directly
- **Rule broken:** Routers must call services only; no Supabase in routers

#### `routers/calendar_accounts.py` — 116 lines
**MEDIUM VIOLATIONS:**
- Defines `_build_calendar_flow()` that duplicates `build_oauth_flow()` in `auth_service.py`
- Defines `SCOPES` list that duplicates `auth_service.py`
- Otherwise properly delegates to `calendar_service`

#### `routers/busy_slots.py` — 39 lines
Clean. Properly delegates to `busy_slots_service`.

#### `routers/auth.py` — 27 lines
Clean. Properly delegates to `auth_service`.

#### `routers/events.py` — 33 lines
Clean. Properly delegates to `event_service`.

#### `routers/participants.py` — 28 lines
Clean. Properly delegates to `participant_service`.

#### `routers/invitations.py` — 19 lines
Clean. Properly delegates to `invitation_service`.

#### `routers/notifications.py` — 28 lines
Clean. Properly delegates to `notification_service`.

#### `routers/calendar_sources.py` — 17 lines
Clean. Properly delegates to `calendar_service`.

#### `routers/finalization.py` — 0 lines
**Ghost file.** Empty — should be deleted.

---

### Services

#### `services/event_service.py` — 287 lines
**HIGH VIOLATIONS:**
- `_fetch_participants()` helper duplicates `_fetch_participants_raw()` in `participant_service.py`
- `delete_event()` inserts notifications directly via `service_client` instead of calling `notification_service.create_notification()` — cross-service direct DB write
- Uses `service_client` (not on CLAUDE.md permitted list for this file)

**LOW VIOLATIONS:**
- All functions raise `HTTPException` — HTTP concern should be in routers only

#### `services/sync_service.py` — 274 lines
**HIGH VIOLATIONS:**
- Credentials construction pattern (`_build_credentials()`) duplicates the same logic in `finalize_service.py`
- Uses `service_client` (not on permitted list)

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/finalize_service.py` — 281 lines
**HIGH VIOLATIONS:**
- Google API call + DB update + notification insertion all in one service — multiple concerns
- Credentials construction duplicated from `sync_service.py`
- Inserts notifications directly via `service_client` instead of calling `notification_service`
- Uses `service_client` (not on permitted list)

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/calendar_service.py` — 201 lines
**HIGH VIOLATIONS:**
- `_build_calendar_flow()` duplicates `build_oauth_flow()` in `auth_service.py`
- Uses `service_client` throughout (not on permitted list)

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/invitation_service.py` — 201 lines
**HIGH VIOLATIONS:**
- `_get_event_by_uid()` private helper duplicates the same pattern in `participant_service.py`, `proposals.py` router, `finalize.py` router, and `busy_slots_service.py` — **5 total copies**
- Uses both `get_authed_client` and `service_client`

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/auth_service.py` — 181 lines
**LOW VIOLATIONS:**
- `build_oauth_flow()` duplicated as `_build_calendar_flow()` in `calendar_accounts.py` router and `calendar_service.py`

Otherwise clean. `service_client` usage is permitted.

#### `services/proposal_service.py` — 175 lines
**MEDIUM VIOLATIONS:**
- Uses `service_client` (not on permitted list)
- Field name mismatch: DB column is `conflicts`, code returns `conflict_count` — bridged manually

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

Single responsibility: clean scheduling algorithm.

#### `services/participant_service.py` — 132 lines
**HIGH VIOLATIONS:**
- `_fetch_participants_raw()` duplicates `_fetch_participants()` in `event_service.py`
- `_fetch_event()` duplicates the get-event-by-uid pattern (one of 5 copies)

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/busy_slots_service.py` — 114 lines (new file)
**MEDIUM VIOLATIONS:**
- `get_event_for_coordinator_sync()` contains another implementation of the get-event-by-uid+auth-check pattern
- Uses `service_client` (not on permitted list)

**LOW VIOLATIONS:**
- All functions raise `HTTPException`

#### `services/notification_service.py` — 102 lines
**HIGH VIOLATIONS:**
- `take_action()` has a **circular import**: `from app.services.invitation_service import respond_to_invitation` inside the function body — import hidden to avoid load-time cycle
- `mark_read` and `mark_all_read` use `service_client` for writes (permitted)

`service_client` usage is permitted for this file.

---

### Models

#### `models/event.py` — 68 lines
**HIGH VIOLATIONS:**
- Defines `ParticipantResponse` which is also defined in `models/participant.py` — **duplicate model**
- `RsvpStatus` defined as `Literal['pending', 'going', 'maybe', 'not_going']` — contradicts `participant.py`'s definition which omits `'pending'`

#### `models/participant.py` — 25 lines
**HIGH VIOLATIONS:**
- `ParticipantResponse` duplicated from `event.py` with different field types (`str` vs `ParticipantStatus`)
- `RsvpStatus` defined as `Literal['going', 'maybe', 'not_going']` — inconsistent with `event.py`
- `status` and `rsvp_status` fields typed as generic `str` instead of Literal

#### `models/invitation.py` — 26 lines
**LOW VIOLATIONS:**
- `status: str` in `InvitationResponse` should be a Literal type

#### `models/notification.py` — 24 lines
**MEDIUM VIOLATIONS:**
- `notification_type: str` and `action_type: str | None` should be Literal types
- `metadata: dict | None` lacks type hints for dict contents

#### `models/calendar.py` — 38 lines
**MEDIUM VIOLATIONS:**
- Uses `Optional[str]` (old typing style) instead of `str | None` — inconsistent with rest of codebase
- `created_at`, `updated_at`, `start_time_utc`, `end_time_utc` typed as `str` instead of `datetime`

#### `models/user.py` — 9 lines
Clean.

#### `models/slot.py` — 0 lines
**CRITICAL:** Empty placeholder. `PreferredSlot` and `ProposedTime` models are defined inline in routers instead of here.

#### `models/__init__.py` — 0 lines
No exports defined. Minor: should re-export all models for cleaner imports.

---

### Backend Summary Table

| File | Lines | Layer OK | service_client OK | HTTPException | Duplication | Inline Models | Priority |
|------|-------|----------|-------------------|---------------|-------------|---------------|----------|
| `routers/proposals.py` | 123 | ❌ | ❌ | — | — | ❌ | **P1** |
| `routers/preferred_slots.py` | 145 | ❌ | ❌ | — | — | ❌ | **P1** |
| `routers/finalize.py` | 116 | ❌ | ❌ | — | ❌ | ❌ | **P1** |
| `routers/calendar_accounts.py` | 116 | ✅ | — | — | ❌ | — | P3 |
| `routers/finalization.py` | 0 | — | — | — | — | — | P3 (delete) |
| `services/event_service.py` | 287 | ✅ | ⚠️ | ❌ | ❌ | — | P2 |
| `services/sync_service.py` | 274 | ✅ | ⚠️ | ❌ | ❌ | — | P2 |
| `services/finalize_service.py` | 281 | ✅ | ⚠️ | ❌ | ❌ | — | P2 |
| `services/calendar_service.py` | 201 | ✅ | ⚠️ | ❌ | ❌ | — | P2 |
| `services/invitation_service.py` | 201 | ✅ | ✅ | ❌ | ❌ | — | P2 |
| `services/auth_service.py` | 181 | ✅ | ✅ | ❌ | ❌ | — | P3 |
| `services/proposal_service.py` | 175 | ✅ | ⚠️ | ❌ | — | — | P3 |
| `services/participant_service.py` | 132 | ✅ | — | ❌ | ❌ | — | P2 |
| `services/busy_slots_service.py` | 114 | ✅ | ⚠️ | ❌ | ❌ | — | P2 |
| `services/notification_service.py` | 102 | ✅ | ✅ | ❌ | — | — | P2 |
| `models/event.py` | 68 | — | — | — | ❌ | — | P2 |
| `models/participant.py` | 25 | — | — | — | ❌ | — | P2 |
| `models/slot.py` | 0 | — | — | — | — | ❌ | **P1** |

**Legend:** ❌ Violation  ✅ Clean  ⚠️ Not on permitted list (grey area — service, not router)

---

## FRONTEND

### Foundation Files

#### `types/index.ts` — 185 lines
Clean. Central type definitions for all major domain entities. Well organized.

#### `lib/api.ts` — 52 lines
Clean. HTTP abstraction layer with token management.

#### `lib/dates.ts`
**MISSING.** No centralized date formatting module exists. Date handling is scattered across components using `new Date()`, `date-fns`, and `toLocaleString()` inconsistently.

#### `lib/utils.ts` — 6 lines
Clean. `cn()` class name utility only.

#### `lib/gridUtils.ts` — 27 lines
Clean. Grid slot overlap detection utilities.

#### `lib/editModeUtils.ts` — 65 lines
**LOW VIOLATIONS:**
- Inline TypeScript interfaces `PendingSlot` and `MergeResult` should be in `types/index.ts`

---

### Stores

#### `stores/authStore.ts` — 33 lines
**LOW VIOLATIONS:**
- Uses `new Date(Date.now() + days * 864e5)` — should use `lib/dates.ts` helper once created

Otherwise clean. Correctly stores only auth state.

#### `stores/notificationStore.ts` — 15 lines
Clean. Stores only unread notification count.

---

### Hooks

#### `hooks/useCalendarAccounts.ts` — 48 lines
Clean.

#### `hooks/useEvent.ts` — 57 lines
Clean.

#### `hooks/useParticipants.ts` — 47 lines
Clean.

#### `hooks/useBusySlots.ts` — 36 lines
Clean.

#### `hooks/usePreferredSlots.ts` — 37 lines
Clean.

#### `hooks/useProposals.ts` — 25 lines
Clean.

#### `hooks/useFinalize.ts` — 35 lines
**LOW VIOLATIONS:**
- Inline TypeScript interface `FinalizeBody` should be in `types/index.ts`

#### `hooks/useNotifications.ts` — 48 lines
Clean.

#### `hooks/useInvitations.ts` — 29 lines
Clean.

---

### Components

#### `components/ui/button.tsx` — 60 lines
Clean.

#### `components/ui/dropdown-menu.tsx` — 268 lines
**LOW VIOLATIONS:**
- Exceeds 200-line component limit (268 lines). Acceptable for a shadcn/ui primitive.

#### `components/ui/popover.tsx` — 75 lines
**LOW VIOLATIONS:**
- Inline `PopoverContextValue` type should be in `types/index.ts`

#### `components/auth/LoginButton.tsx` — 33 lines
Clean.

#### `components/event/InviteInput.tsx` — 70 lines
Clean.

#### `components/event/ParticipantList.tsx` — 122 lines
**LOW VIOLATIONS:**
- Inline `RsvpBadge` sub-component (lines 7–23) should be extracted to `components/event/RsvpBadge.tsx`

#### `components/event/RsvpSelector.tsx` — 56 lines
Clean.

#### `components/notifications/NotificationBell.tsx` — 77 lines
**MEDIUM VIOLATIONS:**
- Contains Supabase real-time subscription setup directly in the component — should be extracted to a `useNotificationSubscription` hook

#### `components/notifications/NotificationList.tsx` — 126 lines
**MEDIUM VIOLATIONS:**
- Inline helper functions `formatLocalTimeRange()` (lines 9–19) and `getFinalizedMessage()` (lines 21–31) should be in `lib/dates.ts` / `lib/`
- Uses `date-fns` library directly instead of routing through `lib/dates.ts`
- Uses `new Date()` for date construction in display context (lines 10, 11, 13, 14, 15, 69)

#### `components/layout/Navbar.tsx` — 76 lines
Clean.

#### `components/dashboard/EventCard.tsx` — 102 lines
**HIGH VIOLATIONS:**
- Inline `formatDateWindow()` helper (lines 5–9) — should be in `lib/dates.ts`
- Inline `EventTypeBadge` sub-component (lines 18–25) — should be extracted
- Inline `StatusBadge` sub-component (lines 27–38) — should be extracted
- Inline `ParticipantAvatars` sub-component (lines 40–71) — should be extracted
- Uses `new Date()` in display code (line 7)

---

### Pages

#### `app/page.tsx` — 313 lines
No violations. Landing page with long-form content; line limit acceptable.

#### `app/dashboard/page.tsx` — 130 lines
**CRITICAL VIOLATIONS:**
- Direct `fetch()` calls on lines 11 and 20 — should use `useEvent()` or similar hook
- Server component pattern bypasses the hooks layer entirely

#### `app/settings/page.tsx` — 188 lines
**MEDIUM VIOLATIONS:**
- Inline `SourceRow` sub-component (lines 142–188) should be extracted to `components/`
- Uses `new Date(...).toLocaleString()` for display (line 124) — should use `lib/dates.ts`
- Inline TypeScript interfaces in JSX props

#### `app/events/new/page.tsx` — 718 lines
**CRITICAL VIOLATIONS:**
- Severely exceeds line limit (718 >> 200)
- Five inline sub-components: `StepIndicator`, `TopNav`, `Step1`, `Step2`, `Step3` — each should be a separate file
- `TopNav` duplicates `components/layout/Navbar.tsx` functionality
- Inline TypeScript types `Step1Values`, `Step2Values`, `WizardData` — should be in `types/index.ts`
- `new Date()` in display code (line 285)
- Direct `api.post()` call in event handler (line 676) — should use a hook mutation
- `console.error()` in production code (line 678)

#### `app/events/[uid]/EventDetailClient.tsx` — 1,614 lines
**EXTREME VIOLATIONS:**
- At 1,614 lines this is the most critical file in the entire codebase
- Contains at least 6 logical sections that should be separate components:
  - `EditModal` — event editing form
  - `DeleteModal` — deletion confirmation
  - `AvailabilityGrid` — complex slot rendering
  - `FinalizeCard` — finalization workflow
  - Proposal display section
  - Grid legend / header
- Slot computation functions (`mergeSlots`, `buildConflictOverlays`, `subtractConflicts`, `buildCountedSegments`, `clipToGridBounds`) duplicate or should live in `lib/gridUtils.ts`
- `formatSlotTime()` should be in `lib/dates.ts`
- Inline TypeScript interfaces `SlotOverlay` and `ConflictOverlay` should be in `types/index.ts`
- 21+ direct `new Date()` usages in display/calculation code
- Inline `StatusBadge`, `typeLabel`, `formatDateWindow` sub-components

#### `app/api/[...path]/route.ts` — 64 lines
Clean. Correct Next.js API proxy pattern.

---

### Frontend Summary Table

| File | Lines | Layer OK | No Direct fetch | No `new Date()` | No Inline Types | No Inline Components | Priority |
|------|-------|----------|-----------------|-----------------|-----------------|----------------------|----------|
| `app/events/[uid]/EventDetailClient.tsx` | 1614 | ✅ | ✅ | ❌ | ❌ | ❌ | **P1** |
| `app/events/new/page.tsx` | 718 | ✅ | ❌ | ❌ | ❌ | ❌ | **P1** |
| `app/dashboard/page.tsx` | 130 | ❌ | ❌ | — | — | — | **P1** |
| `components/dashboard/EventCard.tsx` | 102 | ✅ | ✅ | ❌ | — | ❌ | P2 |
| `components/notifications/NotificationList.tsx` | 126 | ✅ | ✅ | ❌ | — | — | P2 |
| `components/notifications/NotificationBell.tsx` | 77 | ❌ | ✅ | — | — | — | P2 |
| `app/settings/page.tsx` | 188 | ✅ | ✅ | ❌ | ❌ | ❌ | P2 |
| `hooks/useFinalize.ts` | 35 | ✅ | ✅ | — | ❌ | — | P3 |
| `lib/editModeUtils.ts` | 65 | ✅ | ✅ | — | ❌ | — | P3 |
| `components/event/ParticipantList.tsx` | 122 | ✅ | ✅ | — | — | ❌ | P3 |
| `stores/authStore.ts` | 33 | ✅ | ✅ | ❌ | — | — | P3 |
| `lib/dates.ts` | MISSING | — | — | — | — | — | **P1** |

---

## OVERALL PRIORITIES — TOP 10

### P1 — Do Before Modularization Sprint

**1. Create `lib/dates.ts`**  
The module doesn't exist. At least 8 components use `new Date()` directly in display code or reach for `date-fns` individually. Every date formatting and parsing utility in the codebase needs a single home before any refactoring, or extracted components will immediately re-scatter the problem.

**2. Break apart `EventDetailClient.tsx` (1,614 lines)**  
Single most critical file. Extract into: `EditModal`, `DeleteModal`, `AvailabilityGrid`, `FinalizeCard`, and move slot computation functions to `lib/gridUtils.ts`. This file blocks any useful component-level testing or reuse.

**3. Create `preferred_slots_service.py` and move router logic**  
`routers/preferred_slots.py` has **no service layer** — all four CRUD operations call `service_client` directly in the router. This is the most complete layer violation in the backend.

**4. Extract service layer from `routers/proposals.py` and `routers/finalize.py`**  
Both routers call `service_client` directly and define inline Pydantic models. The business logic needs a home (`proposal_service` already exists — move helper functions there; create or extend `finalize_service`).

**5. Fill `models/slot.py`**  
The file is empty. `PreferredSlotCreate`, `PreferredSlotResponse`, `ProposalResponse`, `FinalizeRequest`, and `FinalizeStatusResponse` are all defined inline in their respective routers. Consolidate them here.

**6. Split `app/events/new/page.tsx` (718 lines) into wizard step components**  
Extract `Step1`, `Step2`, `Step3`, `StepIndicator`, and `TopNav` as separate files under `components/event/wizard/`. Also move `Step1Values`, `Step2Values`, and `WizardData` types into `types/index.ts`.

**7. Fix `app/dashboard/page.tsx` layer violation**  
Uses direct `fetch()` calls instead of the hooks layer. Convert to a client component using `useEvent()` hooks, or create a `useEvents()` hook that the dashboard can consume.

### P2 — High Value, Can Be Done During Sprint

**8. Extract `_get_event_by_uid()` into a shared utility (5 copies)**  
`invitation_service.py`, `participant_service.py`, `proposals.py` router, `finalize.py` router, and `busy_slots_service.py` all independently implement the same event-fetch-and-auth-check pattern. Create `services/event_service.py:get_event_or_404()` and call it everywhere.

**9. Extract shared credentials builder from `sync_service.py` and `finalize_service.py`**  
The Google Calendar credential construction block is duplicated in both. Move to a `utils/google_auth.py` helper. Same for `build_oauth_flow()` / `_build_calendar_flow()` duplication between `auth_service.py` and `calendar_service.py` / `calendar_accounts.py`.

**10. Deduplicate `ParticipantResponse` and `RsvpStatus` in models**  
`models/event.py` and `models/participant.py` both define `ParticipantResponse` (with conflicting field types) and `RsvpStatus` (with different Literal values). Consolidate into one definition in `models/participant.py` and import into `models/event.py`.

### P3 — Clean Up Once Higher Priorities Are Done

- Move Supabase real-time subscription from `NotificationBell.tsx` into a `useNotificationSubscription()` hook
- Extract inline sub-components from `EventCard.tsx` (`EventTypeBadge`, `StatusBadge`, `ParticipantAvatars`)
- Extract inline sub-components from `settings/page.tsx` (`SourceRow`) and `ParticipantList.tsx` (`RsvpBadge`)
- Move inline `FinalizeBody` type in `useFinalize.ts` and `PendingSlot`/`MergeResult` in `editModeUtils.ts` to `types/index.ts`
- Move all `HTTPException` raises from services to routers (services return None/raise custom exceptions; routers translate to HTTP)
- Resolve circular import in `notification_service.py:take_action()` by restructuring the invitation response flow
- Delete ghost file `routers/finalization.py` (0 lines)
- Standardize `Optional[X]` vs `X | None` typing style across models
- Add `datetime` types for timestamp fields in `models/calendar.py` instead of `str`
- Explicitly permit or deny `service_client` usage in `calendar_service.py`, `sync_service.py`, `finalize_service.py`, `busy_slots_service.py` in CLAUDE.md

---

*Generated by modularization audit — no code was changed during this process.*
