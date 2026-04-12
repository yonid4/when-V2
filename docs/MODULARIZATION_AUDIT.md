# MODULARIZATION_AUDIT.md — When. v2

**Date:** 2026-04-09 (original) / **Last synced:** 2026-04-11 (HTTPException migration pass)  
**Branch:** modularization  
**Audited against:** `docs/CLAUDE.md` architectural rules  
**Scope:** All files in `backend/app/{routers,services,models,utils,scheduler}/` and `frontend/{hooks,components,app,lib,stores}/`

---

## BACKEND

### Routers

#### `routers/proposals.py`
**CRITICAL VIOLATIONS (original):**
- Defines `ProposalResponse` Pydantic model inline (should be in `models/slot.py`)
- Helper `_get_event_and_check_access()` calls `service_client` directly — business logic + DB access in a router
- Helper `_get_cached_proposals()` calls `service_client` directly
- **Rule broken:** Routers must call services only; no Supabase in routers

**Status: [x] COMPLETE**  
Router now imports `ProposalResponse` from `models/slot.py`. Helpers `get_event_and_check_access` and `get_cached_proposals` moved to `proposal_service.py`. Router only calls service functions.

#### `routers/preferred_slots.py`
**CRITICAL VIOLATIONS (original):**
- Defines `PreferredSlotCreate` and `PreferredSlotResponse` Pydantic models inline (should be in `models/slot.py`)
- Helper `_get_event_and_check_participant()` calls `service_client` directly
- All four CRUD route handlers call `service_client` directly — **no service layer exists for preferred_slots**
- **Rule broken:** Routers must call services only; no Supabase in routers

**Status: [x] COMPLETE**  
Router now imports models from `models/slot.py`. All logic delegated to `preferred_slots_service.py`. Router is 45 lines — clean delegation only.

#### `routers/finalize.py`
**CRITICAL VIOLATIONS (original):**
- Defines `FinalizeRequest` and `FinalizeStatusResponse` Pydantic models inline (should be in `models/`)
- Helper `_get_event_by_uid()` calls `service_client` directly
- GET `/status/{uid}` endpoint body calls `service_client` directly
- **Rule broken:** Routers must call services only; no Supabase in routers

**Status: [x] COMPLETE**  
Router imports models from `models/slot.py`. All logic delegated to `finalize_service.py`. Router is 62 lines — clean delegation. Note: router still contains a `try/except HTTPException` re-raise block for 502/422 error translation — this is correct router-level error handling, not a violation.

#### `routers/calendar_accounts.py`
**MEDIUM VIOLATIONS (original):**
- Defines `_build_calendar_flow()` that duplicates `build_oauth_flow()` in `auth_service.py`
- Defines `SCOPES` list that duplicates `auth_service.py`
- Otherwise properly delegates to `calendar_service`

**Status: [x] COMPLETE**  
Router now imports `build_calendar_flow` from `app/utils/google_auth.py`. No local `SCOPES` or `_build_calendar_flow` definition. Fully clean.

#### `routers/finalization.py` — ghost file
**Status: [x] COMPLETE**  
File deleted. Confirmed absent from filesystem.

#### `routers/busy_slots.py`, `routers/auth.py`, `routers/events.py`, `routers/participants.py`, `routers/invitations.py`, `routers/notifications.py`, `routers/calendar_sources.py`
Clean. No changes needed.

---

### Services

#### `services/event_service.py`
**HIGH VIOLATIONS (original):**
- `_fetch_participants()` helper duplicates `_fetch_participants_raw()` in `participant_service.py`
- `delete_event()` inserts notifications directly via `service_client` instead of calling `notification_service.create_notification()`
- Uses `service_client` (not on CLAUDE.md permitted list for this file)

**Status: [x] COMPLETE**  
- `_fetch_participants_raw()` is now the canonical implementation in `event_service.py`, imported by `participant_service.py` — duplication resolved. ✓  
- `fetch_event_by_uid()` extracted and used as the shared pattern across all services — 5-copy duplication resolved. ✓  
- `service_client` now explicitly permitted in CLAUDE.md for `event_service.py` (event_deleted notifications sent to other users). ✓  
- `delete_event()` now calls `create_notifications()` from `app/utils/notifications.py` instead of inserting directly via `service_client`. ✓  
- **HTTPException migration:** `create_event` — single 500, single caller → moved. Service now returns `None`; router raises 500. All other functions raise 403 AND/OR 404 (disambiguation problem) → left in service. ✓

#### `services/sync_service.py`
**HIGH VIOLATIONS (original):**
- Credentials construction pattern (`_build_credentials()`) duplicates the same logic in `finalize_service.py`
- Uses `service_client` (not on permitted list)

**Status: [x] COMPLETE**  
Both `sync_service.py` and `finalize_service.py` now import `credentials_from_dict` from `app/utils/google_auth.py`. Duplication resolved. `service_client` explicitly permitted in CLAUDE.md.

**HTTPException migration:** No HTTPExceptions exist in this service. Nothing to migrate. ✓

#### `services/finalize_service.py`
**HIGH VIOLATIONS (original):**
- Google API call + DB update + notification insertion all in one service — multiple concerns
- Credentials construction duplicated from `sync_service.py`
- Inserts notifications directly via `service_client` instead of calling `notification_service`
- Uses `service_client` (not on permitted list)

**Status: [x] COMPLETE**  
- Credentials construction deduplicated via `utils/google_auth.py`. ✓  
- `service_client` explicitly permitted in CLAUDE.md. ✓  
- Notifications now routed through `create_notifications()` from `app/utils/notifications.py` instead of direct `service_client` insert. ✓  
- Google Calendar API call extracted to `create_calendar_event()` in `utils/google_auth.py`. `finalize_service.py` imports and delegates to it — GCal I/O is now independently testable. ✓  
- DB write + notification dispatch remain together in the service; splitting would require cross-service transaction coordination with no clear win. Accepted design choice.  
- **HTTPException migration:** `get_finalize_status` — single 403, single caller (`routers/finalize.py`) → moved. Service now returns `None`; router raises 403. `finalize_event` — raises 404/403/422/502 (multi-code) → left in service. ✓

#### `services/calendar_service.py`
**HIGH VIOLATIONS (original):**
- `_build_calendar_flow()` duplicates `build_oauth_flow()` in `auth_service.py`
- Uses `service_client` throughout (not on permitted list)

**Status: [x] COMPLETE**  
`build_calendar_flow` moved to `app/utils/google_auth.py`; `calendar_service.py` no longer defines it. `service_client` explicitly permitted in CLAUDE.md.

**HTTPException migration:** `disconnect_account` — single 403, single caller (`routers/calendar_accounts.py`) → moved. Service now returns `bool`; router raises 403 on `False`. `update_calendar_source` — raises 404 AND 403 (disambiguation problem) → left in service. ✓

#### `services/invitation_service.py`
**HIGH VIOLATIONS (original):**
- `_get_event_by_uid()` private helper duplicates the same pattern in 5 places
- Uses both `get_authed_client` and `service_client`

**Status: [x] COMPLETE**  
`invitation_service.py` now imports `fetch_event_by_uid` from `event_service.py`. Duplication resolved.

**HTTPException migration:** `invite_by_email` — raises 403/409/500 (multi-code) → left in service. `respond_to_invitation` — called by both `routers/invitations.py` and `notification_service.py` (Condition 1 fails: multiple callers) → left in service. ✓

#### `services/auth_service.py`
**LOW VIOLATIONS (original):**
- `build_oauth_flow()` duplicated as `_build_calendar_flow()` in `calendar_accounts.py` and `calendar_service.py`

**Status: [x] COMPLETE**  
`build_calendar_flow` now canonical in `utils/google_auth.py`. No duplication remains. `auth_service.py` retains its own `build_oauth_flow()` for login scope, which is correct.

#### `services/proposal_service.py`
**MEDIUM VIOLATIONS (original):**
- Uses `service_client` (not on permitted list)
- Field name mismatch: DB column is `conflicts`, code returns `conflict_count` — bridged manually

**Status: [x] COMPLETE**  
- `get_event_and_check_access` moved into `proposal_service.py` (previously in router) — clean layering. ✓  
- `service_client` explicitly permitted in CLAUDE.md for this file (reads proposal and event data that requires bypassing RLS for cross-user scoring). ✓  
- **HTTPException migration:** `refresh_proposals` and `get_proposals` both called by `routers/proposals.py` (single caller each), but both raise 403 AND 404 (disambiguation problem) → left in service. ✓

#### `services/participant_service.py`
**HIGH VIOLATIONS (original):**
- `_fetch_participants_raw()` duplicates `_fetch_participants()` in `event_service.py`
- `_fetch_event()` duplicates the get-event-by-uid pattern

**Status: [x] COMPLETE**  
Now imports `_fetch_participants_raw` and `fetch_event_by_uid` from `event_service.py`. All duplication resolved.

**HTTPException migration:** All functions raise 403 AND 404 (disambiguation problem) → left in service. ✓

#### `services/busy_slots_service.py`
**MEDIUM VIOLATIONS (original):**
- `get_event_for_coordinator_sync()` contains another implementation of the get-event-by-uid+auth-check pattern
- Uses `service_client` (not on permitted list)

**Status: [x] COMPLETE**  
Now imports `fetch_event_by_uid` from `event_service.py`. `service_client` explicitly permitted in CLAUDE.md.

**HTTPException migration:** `get_event_busy_slots` — single 403, single caller → moved. `get_event_for_coordinator_sync` — single 403, single caller → moved. Both return `None`; router raises 403. ✓

#### `services/notification_service.py`
**HIGH VIOLATIONS (original):**
- `take_action()` has a **circular import**: `from app.services.invitation_service import respond_to_invitation` inside the function body — import hidden to avoid load-time cycle

**Status: [x] COMPLETE**  
The import of `respond_to_invitation` has been moved from inside the `take_action()` function body to the **top of the file** — the hidden import-inside-function anti-pattern is resolved. ✓  
The dependency `notification_service → invitation_service → event_service` is a clean one-way chain, not a circular import. Python loads it without issue. No restructuring is warranted. ✓

**HTTPException migration:** `mark_read` and `take_action` both raise 404 AND 403 (disambiguation problem) → left in service. ✓

---

### Models

#### `models/slot.py`
**CRITICAL (original):** Empty placeholder. `PreferredSlot` and `ProposedTime` models were defined inline in routers.

**Status: [x] COMPLETE**  
`models/slot.py` now defines: `PreferredSlotCreate`, `PreferredSlotResponse`, `ProposalResponse`, `FinalizeRequest`, `FinalizeStatusResponse`. All five models present.

#### `models/event.py`
**HIGH VIOLATIONS (original):**
- Defines `ParticipantResponse` which is also defined in `models/participant.py` — duplicate model
- `RsvpStatus` inconsistency

**Status: [x] COMPLETE**  
`models/event.py` no longer defines `ParticipantResponse` inline — it imports from `models/participant.py` with a re-export comment. `RsvpStatus` is now defined once in `models/participant.py` as `Literal['pending', 'going', 'maybe', 'not_going']`.

#### `models/participant.py`
**HIGH VIOLATIONS (original):**
- `ParticipantResponse` duplicated from `event.py` with different field types
- `RsvpStatus` inconsistent definition
- `status` and `rsvp_status` fields typed as generic `str` instead of Literal

**Status: [x] COMPLETE**  
`ParticipantResponse` is now the single canonical definition. `status` uses `ParticipantStatus` Literal. `rsvp_status` uses `RsvpStatus | None` Literal. Proper typing throughout.

#### `models/__init__.py`
**Status: [x] COMPLETE**  
Now re-exports all models from all domain files. Clean central imports.

#### `models/invitation.py`
**LOW VIOLATIONS (original):** `status: str` should be a Literal type.

**Status: [x] COMPLETE**  
`InvitationResponse.status` now typed as `Literal['pending', 'accepted', 'declined']`. `Literal` was already imported.

#### `models/notification.py`
**MEDIUM VIOLATIONS (original):** `notification_type: str` and `action_type: str | None` should be Literal types.

**Status: [x] COMPLETE**  
`notification_type` → `Literal['event_invitation', 'invite_accepted', 'event_finalized', 'event_deleted']` (added `'invite_accepted'` which is actively used in `invitation_service.py`). `action_type` → `Literal['accept', 'decline'] | None`. `metadata` has `# TODO: type metadata contents per notification_type` comment.

#### `models/calendar.py`
**MEDIUM VIOLATIONS (original):**
- Uses `Optional[str]` (old typing style) instead of `str | None`
- Timestamp fields typed as `str` instead of `datetime`

**Status: [x] COMPLETE**  
All `Optional[X]` replaced with `X | None`. `CalendarSourceResponse.created_at` and `updated_at` changed to `datetime | None`. `BusySlotResponse.start_time_utc` and `end_time_utc` changed to `datetime` (Pydantic V2 auto-coerces ISO strings from Supabase). `from datetime import datetime` added. `from typing import Optional` removed.

#### `models/user.py`
Clean. No changes needed.

---

### Backend Summary Table

| File | Lines | Layer OK | service_client OK | HTTPException | Duplication | Inline Models | Priority | Status |
|------|-------|----------|-------------------|---------------|-------------|---------------|----------|--------|
| `routers/proposals.py` | ~45 | ✅ | — | — | — | ✅ | **P1** | [x] Done |
| `routers/preferred_slots.py` | ~45 | ✅ | — | — | — | ✅ | **P1** | [x] Done |
| `routers/finalize.py` | ~62 | ✅ | — | — | — | ✅ | **P1** | [x] Done |
| `routers/calendar_accounts.py` | ~94 | ✅ | — | — | ✅ | — | P3 | [x] Done |
| `routers/finalization.py` | 0 | — | — | — | — | — | P3 (delete) | [x] Deleted |
| `services/event_service.py` | ~300 | ✅ | ✅ | [~] | ✅ | — | P2 | [x] Done |
| `services/sync_service.py` | ~274 | ✅ | ✅ | ✅ | ✅ | — | P2 | [x] Done |
| `services/finalize_service.py` | ~281 | ✅ | ✅ | ✅ | ✅ | — | P2 | [x] Done |
| `services/calendar_service.py` | ~201 | ✅ | ✅ | [~] | ✅ | — | P2 | [x] Done |
| `services/invitation_service.py` | ~201 | ✅ | ✅ | [~] | ✅ | — | P2 | [x] Done |
| `services/auth_service.py` | ~181 | ✅ | ✅ | — | ✅ | — | P3 | [x] Done |
| `services/proposal_service.py` | ~175 | ✅ | ✅ | [~] | ✅ | — | P3 | [x] Done |
| `services/participant_service.py` | ~132 | ✅ | — | [~] | ✅ | — | P2 | [x] Done |
| `services/busy_slots_service.py` | ~114 | ✅ | ✅ | [~] | ✅ | — | P2 | [x] Done |
| `services/notification_service.py` | ~102 | ✅ | ✅ | [~] | — | — | P2 | [x] Done |
| `models/event.py` | ~56 | — | — | — | ✅ | — | P2 | [x] Done |
| `models/participant.py` | ~27 | — | — | — | ✅ | — | P2 | [x] Done |
| `models/slot.py` | ~44 | — | — | — | — | ✅ | **P1** | [x] Done |
| `models/invitation.py` | ~26 | — | — | — | — | — | P3 | [x] Done |
| `models/notification.py` | ~24 | — | — | — | — | — | P3 | [x] Done |
| `models/calendar.py` | ~36 | — | — | — | — | — | P3 | [x] Done |

**Legend:** ❌ Violation  ✅ Clean/Fixed  ⚠️ Grey area  [x] Done  [~] Partial  [ ] Pending

---

## FRONTEND

### Foundation Files

#### `lib/dates.ts`
**MISSING (original):** No centralized date formatting module exists.

**Status: [x] COMPLETE**  
`lib/dates.ts` exists with full helper suite: `toDate`, `formatSlotTime`, `formatShortDate`, `formatDateWindow`, `formatDateWindowWithYear`, `formatLocalTimeRange`, `formatDayLabel`, `formatTime`, `formatLongDate`, `formatDateTime`, `getFinalizedMessage`.

#### `lib/gridUtils.ts`
Clean. No changes needed.

#### `lib/editModeUtils.ts`
**LOW VIOLATIONS (original):**
- Inline TypeScript interfaces `PendingSlot` and `MergeResult` should be in `types/index.ts`

**Status: [x] COMPLETE**  
`PendingSlot` and `MergeResult` moved to `types/index.ts`. `editModeUtils.ts` now imports them from `@/types`. All consumer files (`EventDetailClient.tsx`, `AvailabilityGrid.tsx`, `editModeUtils.test.ts`) updated to import from `@/types`.

#### `types/index.ts`
**Status: [x] COMPLETE**  
`Step1Values`, `Step2Values`, `WizardData`, `SlotOverlay`, `ConflictOverlay` all confirmed present in `types/index.ts` (lines 178–215).

#### `lib/api.ts`, `lib/utils.ts`
Clean. No changes needed.

---

### Stores

#### `stores/authStore.ts`
**LOW VIOLATIONS (original):**
- Uses `new Date(Date.now() + days * 864e5)` — should use `lib/dates.ts` helper once created

**Status: [x] COMPLETE**  
`addDays` helper added to `lib/dates.ts`. `authStore.ts` now imports and uses `addDays(new Date(), days)` in `setCookie`.

#### `stores/notificationStore.ts`
Clean. No changes needed.

---

### Hooks

#### `hooks/useFinalize.ts`
**LOW VIOLATIONS (original):**
- Inline TypeScript interface `FinalizeBody` should be in `types/index.ts`

**Status: [x] COMPLETE**  
`FinalizeBody` moved to `types/index.ts`. `useFinalize.ts` now imports it from `@/types`.

#### All other hooks
`useCalendarAccounts.ts`, `useEvent.ts`, `useParticipants.ts`, `useBusySlots.ts`, `usePreferredSlots.ts`, `useProposals.ts`, `useNotifications.ts`, `useInvitations.ts` — Clean.

#### `hooks/useNotificationSubscription.ts` (new file — not in original audit)
**Status: [x] EXTRA — DONE**  
`useNotificationSubscription` hook extracted from `NotificationBell.tsx`. `NotificationBell.tsx` now imports and calls it. P3 item completed ahead of schedule.

---

### Components

#### `components/ui/button.tsx`, `components/ui/dropdown-menu.tsx`
Clean (or acceptable shadcn exceptions). No changes needed.

#### `components/ui/popover.tsx`
**LOW VIOLATION (original):** Inline `PopoverContextValue` interface should be in `types/index.ts`.

**Status: [x] COMPLETE**  
`PopoverContextValue` moved to `types/index.ts`. `popover.tsx` now imports it from `@/types`.

#### `components/auth/LoginButton.tsx`
Clean. No changes needed.

#### `components/event/InviteInput.tsx`, `components/event/RsvpSelector.tsx`
Clean. No changes needed.

#### `components/event/ParticipantList.tsx`
**LOW VIOLATIONS (original):**
- Inline `RsvpBadge` sub-component (lines 7–23) should be extracted to `components/event/RsvpBadge.tsx`

**Status: [x] COMPLETE**  
`RsvpBadge` extracted to `components/event/RsvpBadge.tsx` (default export). `ParticipantList.tsx` imports it from `@/components/event/RsvpBadge`.

#### `components/notifications/NotificationBell.tsx`
**MEDIUM VIOLATIONS (original):**
- Contains Supabase real-time subscription setup directly in the component

**Status: [x] COMPLETE**  
Supabase subscription extracted to `hooks/useNotificationSubscription.ts`. `NotificationBell.tsx` now calls `useNotificationSubscription(user?.id)`. Component is clean.

#### `components/notifications/NotificationList.tsx`
**MEDIUM VIOLATIONS (original):**
- Inline `formatLocalTimeRange()` and `getFinalizedMessage()` should be in `lib/dates.ts`
- Uses `date-fns` directly; uses `new Date()` in display code

**Status: [x] COMPLETE**  
`formatLocalTimeRange` and `getFinalizedMessage` now imported from `lib/dates.ts`. `getFinalizedMessage` used directly for `event_finalized` notifications. Still uses `date-fns/formatDistanceToNow` and `new Date(n.created_at)` for relative time display (line 46) — this is acceptable: `formatDistanceToNow` needs a `Date` object and the conversion is trivial/non-display.

#### `components/dashboard/EventCard.tsx`
**HIGH VIOLATIONS (original):**
- Inline `formatDateWindow()` helper — should be in `lib/dates.ts`
- Inline `EventTypeBadge`, `StatusBadge`, `ParticipantAvatars` sub-components — should be extracted

**Status: [x] COMPLETE**  
`EventCard.tsx` now imports `formatDateWindow` from `lib/dates.ts`. `EventTypeBadge`, `StatusBadge`, and `ParticipantAvatars` are extracted to separate files under `components/dashboard/`. `EventCard.tsx` is now 38 lines — clean.

#### `components/layout/Navbar.tsx`
Clean. No changes needed.

---

### Pages

#### `app/page.tsx`
No violations. No changes needed.

#### `app/dashboard/page.tsx`
**CRITICAL VIOLATIONS (original):**
- Direct `fetch()` calls — should use `useEvent()` or similar hook
- Server component pattern bypasses hooks layer

**Status: [x] COMPLETE**  
`dashboard/page.tsx` is now a client component (`'use client'`) using `useEvents()` and `useCalendarAccounts()` hooks. No direct `fetch()` calls. 

#### `app/settings/page.tsx`
**MEDIUM VIOLATIONS (original):**
- Inline `SourceRow` sub-component should be extracted
- Uses `new Date(...).toLocaleString()` — should use `lib/dates.ts`
- Inline TypeScript interfaces in JSX props

**Status: [x] COMPLETE**  
`SourceRow` extracted to `components/settings/SourceRow.tsx`. Settings page imports `formatDateTime` from `lib/dates.ts`.

#### `app/events/new/page.tsx`
**CRITICAL VIOLATIONS (original):**
- 718 lines; five inline sub-components
- Inline TypeScript types `Step1Values`, `Step2Values`, `WizardData`
- Direct `api.post()` in event handler
- `console.error()` in production code

**Status: [x] COMPLETE**  
Page is now ~65 lines. `Step1`, `Step2`, `Step3`, `StepIndicator` extracted to `components/event/wizard/`. Types moved to `types/index.ts`. `inviteParticipant` hook mutation used instead of direct `api.post()`. No `console.error()`. Note: `TopNav` was not extracted separately — the shared `<Navbar />` component is used instead. Correct.

#### `app/events/[uid]/EventDetailClient.tsx`
**EXTREME VIOLATIONS (original):** 1,614 lines; 6+ embedded components; slot computation functions; inline types; 21+ `new Date()` usages.

**Status: [x] COMPLETE**  
- `EditModal` and `DeleteModal` extracted to `components/event/EditModal.tsx` and `components/event/DeleteModal.tsx`. ✓  
- `AvailabilityGrid` extracted to `components/event/AvailabilityGrid.tsx`. ✓  
- `StatusBadge` extracted to `components/event/StatusBadge.tsx`. ✓  
- `FinalizeCard` extracted to `app/events/[uid]/FinalizeCard.tsx`, imported and rendered as modal. ✓  
- `ProposalList` extracted to `app/events/[uid]/ProposalList.tsx`. ✓  
- `GridHeader` extracted to `app/events/[uid]/GridHeader.tsx`. ✓  
- Slot computation functions (`mergeSlots`, `buildConflictOverlays`, `subtractConflicts`, `buildCountedSegments`) — confirmed absent from codebase; superseded by `useAvailabilitySegments` hook. `clipToGridBounds` lives in `lib/gridUtils.ts`. ✓  
- All `new Date()` usages in file are Date object construction for drag/resize coordinate math — not display code, not CLAUDE.md violations. ✓  
- File is 673 lines. No inline components, no inline types, no display `new Date()` calls.

#### `app/api/[...path]/route.ts`
Clean. No changes needed.

---

### Frontend Summary Table

| File | Lines | Layer OK | No Direct fetch | No `new Date()` | No Inline Types | No Inline Components | Priority | Status |
|------|-------|----------|-----------------|-----------------|-----------------|----------------------|----------|--------|
| `app/events/[uid]/EventDetailClient.tsx` | 673 | ✅ | ✅ | ✅ | ✅ | ✅ | **P1→P2** | [x] Done |
| `app/events/new/page.tsx` | ~65 | ✅ | ✅ | ⚠️ | ✅ | ✅ | **P1** | [x] Done |
| `app/dashboard/page.tsx` | ~70 | ✅ | ✅ | — | — | — | **P1** | [x] Done |
| `components/dashboard/EventCard.tsx` | ~38 | ✅ | ✅ | ✅ | — | ✅ | P2 | [x] Done |
| `components/notifications/NotificationList.tsx` | ~100 | ✅ | ✅ | ✅ | — | — | P2 | [x] Done |
| `components/notifications/NotificationBell.tsx` | ~49 | ✅ | ✅ | — | — | — | P2 | [x] Done |
| `app/settings/page.tsx` | ~? | ✅ | ✅ | ✅ | — | ✅ | P2 | [x] Done |
| `hooks/useFinalize.ts` | ~27 | ✅ | ✅ | — | ✅ | — | P3 | [x] Done |
| `lib/editModeUtils.ts` | ~53 | ✅ | ✅ | — | ✅ | — | P3 | [x] Done |
| `components/event/ParticipantList.tsx` | ~100 | ✅ | ✅ | — | — | ✅ | P3 | [x] Done |
| `stores/authStore.ts` | ~33 | ✅ | ✅ | ✅ | — | — | P3 | [x] Done |
| `lib/dates.ts` | ~112 | ✅ | — | — | — | — | **P1** | [x] Done |

---

## Audit Summary — 2026-04-11 (final sync)

### P1 items: 7 complete, 0 pending

| Item | Status |
|------|--------|
| Create `lib/dates.ts` | [x] Done |
| Break apart `EventDetailClient.tsx` | [x] Done (EditModal, DeleteModal, AvailabilityGrid, FinalizeCard, ProposalList, GridHeader all extracted; slot computation functions confirmed absent from file) |
| Create `preferred_slots_service.py` and move router logic | [x] Done |
| Extract service layer from `routers/proposals.py` and `routers/finalize.py` | [x] Done |
| Fill `models/slot.py` | [x] Done |
| Split `app/events/new/page.tsx` into wizard step components | [x] Done |
| Fix `app/dashboard/page.tsx` layer violation | [x] Done |

### P2 items: 8 complete, 0 pending

| Item | Status |
|------|--------|
| Extract `_get_event_by_uid()` into shared utility | [x] Done (`fetch_event_by_uid` in `event_service.py`) |
| Deduplicate credentials builder (`utils/google_auth.py`) | [x] Done |
| Deduplicate `ParticipantResponse` and `RsvpStatus` | [x] Done |
| Roll out `lib/dates.ts` to `NotificationList.tsx`, `EventCard.tsx`, `settings/page.tsx` | [x] Done |
| Extract `EventDetailClient.tsx` — `FinalizeCard` component | [x] Done (imported from `./FinalizeCard`, rendered as modal) |
| Extract remaining inline sub-components from `EventCard.tsx` | [x] Done (EventTypeBadge, StatusBadge, ParticipantAvatars all extracted) |
| `finalize_service.py` — notifications via `notification_service` not direct insert | [x] Done |
| `event_service.py` delete_event — notifications via helper not direct insert | [x] Done |

### P3 items: 12 complete, 0 pending

| Item | Status |
|------|--------|
| Move Supabase real-time subscription from `NotificationBell.tsx` into `useNotificationSubscription()` hook | [x] Done (ahead of schedule) |
| Delete ghost file `routers/finalization.py` | [x] Done |
| Explicitly permit `service_client` usage in relevant service files in CLAUDE.md | [x] Done |
| Standardize `Optional[X]` vs `X | None` in `models/calendar.py` | [x] Done |
| Add `datetime` types for timestamp fields in `models/calendar.py` | [x] Done |
| Move `FinalizeBody` type in `useFinalize.ts` to `types/index.ts` | [x] Done |
| Move `PendingSlot`/`MergeResult` in `editModeUtils.ts` to `types/index.ts` | [x] Done |
| Extract `RsvpBadge` from `ParticipantList.tsx` | [x] Done |
| Resolve circular import in `notification_service.py:take_action()` | [x] Done — import moved to module top; dependency is a clean one-way chain, not a cycle |
| Move `HTTPException` raises from all service files to router-level | [x] Done — migrated where safe (single code + single caller); remainder left intentionally (disambiguation) |
| Add Literal types to `models/invitation.py` (`status`) | [x] Done |
| Add Literal types to `models/notification.py` (`notification_type`, `action_type`) | [x] Done |

### Items closed with notes

- **`notification_service.py` circular import** — import moved to module top; confirmed no real circular dependency (`notification_service → invitation_service → event_service` is a one-way chain). No further restructuring needed.
- **`EventDetailClient.tsx` slot computation functions** — verified: `mergeSlots`, `buildConflictOverlays`, `subtractConflicts`, `buildCountedSegments` do not exist anywhere in the codebase; superseded by `useAvailabilitySegments` hook. `clipToGridBounds` is in `lib/gridUtils.ts`. File is 673 lines — all extraction work complete.
- **`stores/authStore.ts` `new Date()` usage** — resolved: `addDays` added to `lib/dates.ts` and used in `setCookie`.

---

*Audit synced against actual codebase on 2026-04-11. Checkbox states verified by reading files — not inferred from git history.*
