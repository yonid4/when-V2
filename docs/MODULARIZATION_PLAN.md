# Modularization Plan — When. v2

**Source:** `docs/MODULARIZATION_AUDIT.md`
**Date:** 2026-04-09
**Branch:** sprint5

Each priority group should be fully complete before the next begins — P2 items that depend on P1 foundations will break if done out of order.

---

## P1 — Do Before Anything Else

### Backend — Models

- [x] Fill `backend/app/models/slot.py` with `PreferredSlotCreate`, `PreferredSlotResponse`, `ProposalResponse`, `FinalizeRequest`, and `FinalizeStatusResponse` models (file is currently empty)
- [x] Move `PreferredSlotCreate` and `PreferredSlotResponse` inline models from `backend/app/routers/preferred_slots.py` into `backend/app/models/slot.py`
- [x] Move `ProposalResponse` inline model from `backend/app/routers/proposals.py` into `backend/app/models/slot.py`
- [x] Move `FinalizeRequest` and `FinalizeStatusResponse` inline models from `backend/app/routers/finalize.py` into `backend/app/models/slot.py`

### Backend — New Service Files

- [x] Create `backend/app/services/preferred_slots_service.py` and move all four CRUD operations out of `backend/app/routers/preferred_slots.py` (no service layer currently exists)

### Backend — Router Cleanup

- [x] Remove `_get_event_and_check_participant()` helper from `backend/app/routers/preferred_slots.py` and replace with service call
- [x] Remove `_get_event_and_check_access()` helper from `backend/app/routers/proposals.py` and replace with service call
- [x] Remove `_get_cached_proposals()` helper from `backend/app/routers/proposals.py` and replace with service call
- [x] Remove `_get_event_by_uid()` helper from `backend/app/routers/finalize.py` and replace with service call
- [x] Remove direct `service_client` usage from `backend/app/routers/finalize.py` GET `/status/{uid}` endpoint body and route through `finalize_service`

### Frontend — Foundation

- [x] Create `frontend/lib/dates.ts` with timezone-aware date formatting and parsing helpers (currently missing; required by all other frontend fixes)

### Frontend — Type Consolidation

- [x] Move `Step1Values`, `Step2Values`, and `WizardData` inline types from `app/events/new/page.tsx` into `types/index.ts`
- [x] Move `SlotOverlay` and `ConflictOverlay` inline interfaces from `app/events/[uid]/EventDetailClient.tsx` into `types/index.ts`

### Frontend — Dashboard Fix

- [x] Fix `app/dashboard/page.tsx` to remove direct `fetch()` calls (lines 11 and 20) and use `useEvent()` or a new `useEvents()` hook instead

### Frontend — Split `app/events/new/page.tsx`

- [x] Extract `StepIndicator` from `app/events/new/page.tsx` into `components/event/wizard/StepIndicator.tsx`
- [x] Extract `TopNav` from `app/events/new/page.tsx` into `components/event/wizard/TopNav.tsx` (and reconcile duplication with `components/layout/Navbar.tsx`)
- [x] Extract `Step1` from `app/events/new/page.tsx` into `components/event/wizard/Step1.tsx`
- [x] Extract `Step2` from `app/events/new/page.tsx` into `components/event/wizard/Step2.tsx`
- [x] Extract `Step3` from `app/events/new/page.tsx` into `components/event/wizard/Step3.tsx`
- [x] Replace direct `api.post()` call in event handler (line 676) in `app/events/new/page.tsx` with a hook mutation
- [x] Remove `console.error()` from production code in `app/events/new/page.tsx` (line 678)
- [x] Replace `new Date()` usage in display code in `app/events/new/page.tsx` (line 285) with `lib/dates.ts` helper

### Frontend — Split `EventDetailClient.tsx`

- [x] Move `mergeSlots`, `buildConflictOverlays`, `subtractConflicts`, `buildCountedSegments`, `clipToGridBounds` from `app/events/[uid]/EventDetailClient.tsx` into `lib/gridUtils.ts`
- [x] Move `formatSlotTime()` from `app/events/[uid]/EventDetailClient.tsx` into `lib/dates.ts`
- [x] Extract inline `StatusBadge`, `typeLabel`, and `formatDateWindow` from `app/events/[uid]/EventDetailClient.tsx` into appropriate component or lib files
- [x] Replace all 21+ direct `new Date()` usages in display/calculation code in `app/events/[uid]/EventDetailClient.tsx` with `lib/dates.ts` helpers
- [x] Extract `EditModal` section from `app/events/[uid]/EventDetailClient.tsx` into `components/event/EditModal.tsx`
- [x] Extract `DeleteModal` section from `app/events/[uid]/EventDetailClient.tsx` into `components/event/DeleteModal.tsx`
- [x] Extract `AvailabilityGrid` section from `app/events/[uid]/EventDetailClient.tsx` into `components/event/AvailabilityGrid.tsx`
- [x] Extract `FinalizeCard` section from `app/events/[uid]/EventDetailClient.tsx` into `components/event/FinalizeCard.tsx`
- [x] Extract proposal display section from `app/events/[uid]/EventDetailClient.tsx` into a dedicated component
- [x] Extract grid legend/header section from `app/events/[uid]/EventDetailClient.tsx` into a dedicated component

---

## P2 — High Value, Do During Sprint

### Backend — Shared Utilities

- [ ] Create `backend/app/utils/google_auth.py` with a shared credentials builder helper (to be used by `sync_service.py` and `finalize_service.py`)
- [ ] Move `build_oauth_flow()` / `_build_calendar_flow()` to `backend/app/utils/google_auth.py` and remove the duplicate from `backend/app/services/calendar_service.py`

### Backend — Service Deduplication

- [ ] Remove duplicated credentials construction block from `backend/app/services/sync_service.py` and replace with `utils/google_auth.py` call
- [ ] Remove duplicated credentials construction block from `backend/app/services/finalize_service.py` and replace with `utils/google_auth.py` call
- [ ] Add `get_event_or_404()` shared utility to `backend/app/services/event_service.py` (currently 5 separate implementations of the same pattern)
- [ ] Replace `_get_event_by_uid()` / `_get_event()` in `backend/app/services/invitation_service.py` with call to `event_service.get_event_or_404()`
- [ ] Replace `_fetch_event()` in `backend/app/services/participant_service.py` with call to `event_service.get_event_or_404()`
- [ ] Replace `get_event_for_coordinator_sync()` event-fetch pattern in `backend/app/services/busy_slots_service.py` with call to `event_service.get_event_or_404()`
- [ ] Replace `_get_event_and_check_access()` in `backend/app/routers/proposals.py` with call to `event_service.get_event_or_404()` (after service extraction above)
- [ ] Replace `_get_event_by_uid()` in `backend/app/routers/finalize.py` with call to `event_service.get_event_or_404()` (after service extraction above)
- [ ] Remove `_fetch_participants()` duplicate from `backend/app/services/event_service.py` and use `participant_service._fetch_participants_raw()` (or a shared export)
- [ ] Remove `_fetch_participants_raw()` duplicate from `backend/app/services/participant_service.py` and consolidate with the canonical version
- [ ] Replace direct `service_client` notification insertion in `backend/app/services/event_service.py:delete_event()` with a call to `notification_service.create_notification()`
- [ ] Replace direct `service_client` notification insertion in `backend/app/services/finalize_service.py` with calls to `notification_service.create_notification()`
- [ ] Resolve circular import in `backend/app/services/notification_service.py:take_action()` (currently imports `invitation_service.respond_to_invitation` inside function body to avoid load-time cycle)

### Backend — Router Cleanup

- [ ] Remove `_build_calendar_flow()` duplicate from `backend/app/routers/calendar_accounts.py` and use the shared helper from `backend/app/utils/google_auth.py`
- [ ] Remove duplicate `SCOPES` list from `backend/app/routers/calendar_accounts.py` and import from `auth_service.py` or the shared util

### Backend — Models

- [ ] Consolidate `ParticipantResponse` into a single definition in `backend/app/models/participant.py` and remove the duplicate from `backend/app/models/event.py`
- [ ] Consolidate `RsvpStatus` into a single canonical `Literal` definition in `backend/app/models/participant.py` and remove the duplicate from `backend/app/models/event.py`

### Frontend — `lib/dates.ts` Rollout

- [ ] Extract `formatLocalTimeRange()` helper (lines 9–19) from `components/notifications/NotificationList.tsx` into `lib/dates.ts`
- [ ] Extract `getFinalizedMessage()` helper (lines 21–31) from `components/notifications/NotificationList.tsx` into `lib/dates.ts`
- [ ] Replace direct `date-fns` usage in `components/notifications/NotificationList.tsx` with helpers from `lib/dates.ts`
- [ ] Replace all `new Date()` usages in display code in `components/notifications/NotificationList.tsx` with `lib/dates.ts` helpers
- [ ] Move `formatDateWindow()` inline helper (lines 5–9) from `components/dashboard/EventCard.tsx` into `lib/dates.ts`
- [ ] Replace `new Date()` usage in display code in `components/dashboard/EventCard.tsx` (line 7) with `lib/dates.ts` helper
- [ ] Replace `new Date(...).toLocaleString()` in `app/settings/page.tsx` (line 124) with `lib/dates.ts` helper

### Frontend — Component Extractions

- [ ] Extract Supabase real-time subscription from `components/notifications/NotificationBell.tsx` into a `useNotificationSubscription` hook
- [ ] Extract `EventTypeBadge` inline sub-component (lines 18–25) from `components/dashboard/EventCard.tsx` into a separate component file
- [ ] Extract `StatusBadge` inline sub-component (lines 27–38) from `components/dashboard/EventCard.tsx` into a separate component file
- [ ] Extract `ParticipantAvatars` inline sub-component (lines 40–71) from `components/dashboard/EventCard.tsx` into a separate component file
- [ ] Extract `SourceRow` inline sub-component (lines 142–188) from `app/settings/page.tsx` into `components/`
- [ ] Remove inline TypeScript interfaces from JSX props in `app/settings/page.tsx` and move to `types/index.ts`

---

## P3 — Clean Up Once Higher Priorities Are Done

### Backend — `HTTPException` Migration

- [ ] Move all `HTTPException` raises from `backend/app/services/event_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/sync_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/finalize_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/calendar_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/invitation_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/proposal_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/participant_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/busy_slots_service.py` to the calling router
- [ ] Move all `HTTPException` raises from `backend/app/services/notification_service.py` to the calling router

### Backend — Model Polish

- [ ] Fix field name mismatch in `backend/app/services/proposal_service.py`: DB column is `conflicts` but code returns `conflict_count`
- [ ] Add `Literal` type to `status` field in `backend/app/models/invitation.py:InvitationResponse` (currently `str`)
- [ ] Add `Literal` type to `notification_type` field in `backend/app/models/notification.py` (currently `str`)
- [ ] Add `Literal` type to `action_type` field in `backend/app/models/notification.py` (currently `str | None`)
- [ ] Add typed dict contents for `metadata: dict | None` in `backend/app/models/notification.py`
- [ ] Replace `Optional[str]` with `str | None` throughout `backend/app/models/calendar.py` for consistency
- [ ] Change `created_at`, `updated_at`, `start_time_utc`, `end_time_utc` fields in `backend/app/models/calendar.py` from `str` to `datetime`
- [ ] Add canonical `RsvpStatus` literal to `backend/app/models/participant.py` — include `'pending'` value to match `event.py` usage (or explicitly exclude and update all callers)
- [ ] Fix `status` and `rsvp_status` fields in `backend/app/models/participant.py` from generic `str` to the canonical `RsvpStatus` Literal

### Backend — Housekeeping

- [ ] Delete ghost file `backend/app/routers/finalization.py` (0 lines, empty)
- [ ] Add re-exports for all models in `backend/app/models/__init__.py` (currently empty)
- [ ] Update `docs/CLAUDE.md` to explicitly permit or deny `service_client` usage in `calendar_service.py`, `sync_service.py`, `finalize_service.py`, and `busy_slots_service.py`

### Frontend — Type Consolidation

- [ ] Move `FinalizeBody` inline interface from `hooks/useFinalize.ts` into `types/index.ts`
- [ ] Move `PendingSlot` inline interface from `lib/editModeUtils.ts` into `types/index.ts`
- [ ] Move `MergeResult` inline interface from `lib/editModeUtils.ts` into `types/index.ts`
- [ ] Move inline `PopoverContextValue` type from `components/ui/popover.tsx` into `types/index.ts`

### Frontend — Component Polish

- [ ] Extract `RsvpBadge` inline sub-component (lines 7–23) from `components/event/ParticipantList.tsx` into `components/event/RsvpBadge.tsx`
- [ ] Replace `new Date(Date.now() + days * 864e5)` in `stores/authStore.ts` with a `lib/dates.ts` helper
