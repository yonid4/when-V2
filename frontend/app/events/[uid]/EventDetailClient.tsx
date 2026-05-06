'use client'

import { useState, useEffect, useCallback, useRef } from 'react'
import {
  MapPin,
  Trash2,
  Pencil,
  CalendarDays,
  RefreshCw,
  UserPlus,
  Link2,
  RefreshCcw,
  Calendar,
  CalendarCheck,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useEvent } from '@/hooks/useEvent'
import { useSyncCalendar, useSyncMyCalendar } from '@/hooks/useBusySlots'
import { usePreferredSlots, useSavePreferredSlot, useDeletePreferredSlot } from '@/hooks/usePreferredSlots'
import { useAvailabilitySegments } from '@/hooks/useAvailabilitySegments'
import { useProposals, useRefreshProposals } from '@/hooks/useProposals'
import { useProposalFreshness } from '@/hooks/useProposalFreshness'
import { FinalizeCard } from './FinalizeCard'
import { ProposalList } from './ProposalList'
import { GridHeader } from './GridHeader'
import { useEventSubscriptions, useEventPresence } from '@/hooks/useEventSubscriptions'
import { ParticipantList } from '@/components/event/ParticipantList'
import { InviteInput } from '@/components/event/InviteInput'
import { RsvpSelector } from '@/components/event/RsvpSelector'
import { Navbar } from '@/components/layout/Navbar'
import { useAuthStore } from '@/stores/authStore'
import type { EventWithParticipants, PreferredSlot } from '@/types'
import { toDate, formatDateWindowWithYear, formatTime, formatLongDate } from '@/lib/dates'
import { typeLabel } from '@/lib/eventUtils'
import { StatusBadge } from '@/components/event/StatusBadge'
import { EditModal } from '@/components/event/EditModal'
import { DeleteModal } from '@/components/event/DeleteModal'
import { AvailabilityGrid } from '@/components/event/AvailabilityGrid'
import { ProposedTimeOverlay } from '@/components/event/ProposedTimeOverlay'
import { computeMerge } from '@/lib/editModeUtils'
import type { PendingSlot } from '@/types'
import type { EditSaveResult } from './editEventUtils'
import EventNotFound from './not-found'


// ─── Helpers ──────────────────────────────────────────────────────────────────

// Stable empty array — used as the default for usePreferredSlots so that the
// inline `= []` default doesn't create a new reference every render, which
// would cause the preferredSlotsRef comparison in the sync effect to always
// be true and trigger an infinite setState loop.
const EMPTY_PREFERRED_SLOTS: PreferredSlot[] = []

// ─── Main export ─────────────────────────────────────────────────────────────

export default function EventDetailClient({ uid }: { uid: string }) {
  const { data: event, isLoading, error } = useEvent(uid)
  if (error) return <EventNotFound />
  if (isLoading || !event) return <EventDetailSkeleton />
  return <EventDetailLoaded event={event} />
}

function EventDetailSkeleton() {
  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Navbar />
      <main className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">
        <section className="flex-1 min-h-0 flex flex-col overflow-hidden p-4 md:p-6 lg:p-8 bg-surface">
          <div className="flex flex-col flex-1 gap-4 min-h-0">
            <div className="h-8 w-48 rounded bg-surface-container-high animate-pulse" />
            <div className="flex-1 min-h-0 rounded-lg bg-surface-container-low animate-pulse" />
          </div>
        </section>
        <section className="w-full md:w-[400px] shrink-0 lg:w-[456px] xl:w-[504px] md:h-full overflow-y-auto bg-surface-container-low p-4 md:p-6 flex flex-col gap-6">
          <div className="bg-surface-container-lowest p-6 rounded-lg space-y-3">
            <div className="h-4 w-24 rounded bg-surface-container-high animate-pulse" />
            <div className="h-8 w-3/4 rounded bg-surface-container-high animate-pulse" />
            <div className="h-4 w-1/2 rounded bg-surface-container-high animate-pulse" />
          </div>
          <div className="h-12 rounded-xl bg-surface-container-high animate-pulse" />
          <div className="h-32 rounded-xl bg-surface-container-high animate-pulse" />
        </section>
      </main>
    </div>
  )
}

function EventDetailLoaded({ event }: { event: EventWithParticipants }) {
  const { user } = useAuthStore()
  const currentUserId = user?.id ?? ''

  const [participantsKey, setParticipantsKey] = useState(0)

  const isCoordinator = !!user?.id && user.id === event.coordinator_id

  const [showEdit, setShowEdit] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showInvite, setShowInvite] = useState(false)
  const [copyLabel, setCopyLabel] = useState('Copy Link')

  // ── Edit mode state ──────────────────────────────────────────────────────
  const [isEditMode, setIsEditMode] = useState(false)
  const [pendingSlot, setPendingSlot] = useState<PendingSlot | null>(null)
  const [dragState, setDragState] = useState<{ dayIndex: number; anchorCellStartUtc: Date; baseDate: Date } | null>(null)
  const [resizeState, setResizeState] = useState<{ edge: 'top' | 'bottom' } | null>(null)
  const [slotsToDelete, setSlotsToDelete] = useState<string[]>([])
  const [displayedPreferredSlots, setDisplayedPreferredSlots] = useState<PreferredSlot[]>([])
  const [doneError, setDoneError] = useState<string | null>(null)
  const [isDonePending, setIsDonePending] = useState(false)
  const [deletingSlotId, setDeletingSlotId] = useState<string | null>(null)

  // ── Proposals state ──────────────────────────────────────────────────────
  const [proposalsEnabled, setProposalsEnabled] = useState(false)
  const [showProposedOverlay, setShowProposedOverlay] = useState(false)
  const [proposalsStale, setProposalsStale] = useState(false)
  const [showFinalizeCard, setShowFinalizeCard] = useState(false)

  const queryClient = useQueryClient()

  function handleSave(result: EditSaveResult) {
    if (result.infoChanged || result.timeRangeChanged) {
      queryClient.invalidateQueries({ queryKey: ['events', event.uid] })
    }
    if (result.timeRangeChanged) {
      queryClient.refetchQueries({ queryKey: ['busy-slots', 'event', event.uid] })
      queryClient.refetchQueries({ queryKey: ['preferred-slots', event.uid] })
      queryClient.refetchQueries({ queryKey: ['availability-segments', event.uid] })
    }
    if (result.guestInvitesChanged) {
      setParticipantsKey((k) => k + 1)
    }
  }
  const { data: segments = [] } = useAvailabilitySegments(event.uid)
  const { data: preferredSlots = EMPTY_PREFERRED_SLOTS } = usePreferredSlots(event.uid)
  const { mutate: syncCalendar, isPending: isSyncing } = useSyncMyCalendar()
  const { mutateAsync: savePreferredSlot } = useSavePreferredSlot(event.uid)
  const { mutateAsync: deletePreferredSlot } = useDeletePreferredSlot(event.uid)

  // Keep displayed preferred slots in sync with fetched data (when not in edit mode)
  const preferredSlotsRef = useRef<PreferredSlot[]>([])
  useEffect(() => {
    if (!isEditMode && preferredSlots !== preferredSlotsRef.current) {
      preferredSlotsRef.current = preferredSlots as PreferredSlot[]
      setDisplayedPreferredSlots(preferredSlots as PreferredSlot[])
    }
  }, [preferredSlots, isEditMode])

  // Real-time: all event subscriptions via broadcast channels
  useEventSubscriptions(event.uid, event.id, currentUserId || undefined)

  // Presence: who else is viewing this event right now
  const presentUsers = useEventPresence(event.uid, user ?? null)

  const { mutate: syncAll, isPending: isSyncingAll } = useSyncCalendar(event.uid)

  const { data: proposals, isLoading: isLoadingProposals } = useProposals(event.uid, proposalsEnabled)
  const { mutate: refreshProposals, isPending: isRefreshing } = useRefreshProposals(event.uid)
  const { isChecking: isCheckingProposals, checkAndRefreshIfNeeded } = useProposalFreshness(event.uid)

  async function handleViewProposedTimes() {
    if (showProposedOverlay) {
      setShowProposedOverlay(false)
      return
    }
    if (isCoordinator) {
      await checkAndRefreshIfNeeded()
      setProposalsStale(false)
    }
    setProposalsEnabled(true)
    setShowProposedOverlay(true)
  }

  function runMergeCheck(
    pending: PendingSlot,
    allConfirmedSlots: PreferredSlot[],
    weekBaseDate: Date
  ) {
    const result = computeMerge(
      pending,
      allConfirmedSlots,
      (slot) => {
        const slotDate = toDate(slot.start_time_utc)
        for (let i = 0; i < 7; i++) {
          const colDate = new Date(weekBaseDate)
          colDate.setDate(colDate.getDate() + i)
          if (
            slotDate.getFullYear() === colDate.getFullYear() &&
            slotDate.getMonth() === colDate.getMonth() &&
            slotDate.getDate() === colDate.getDate()
          ) {
            return i
          }
        }
        return -1
      }
    )
    const foreignSlots = (preferredSlots as PreferredSlot[]).filter(
      (s) => s.user_id !== user?.id
    )
    setPendingSlot(result.pendingSlot)
    setSlotsToDelete(result.slotsToDelete)
    // Keep foreign slots visible alongside the remaining own slots
    setDisplayedPreferredSlots([...result.remainingSlots, ...foreignSlots])
  }

  // Mouse-up handler — global, attached when dragging or resizing
  const handleDocumentMouseUp = useCallback(() => {
    const ownSlots = (preferredSlots as PreferredSlot[]).filter(
      (s) => s.user_id === user?.id
    )
    if (pendingSlot && dragState) {
      runMergeCheck(pendingSlot, ownSlots, dragState.baseDate)
    } else if (pendingSlot && resizeState) {
      // For resize, derive baseDate from the pending slot's startUtc
      const bd = new Date(pendingSlot.startUtc)
      bd.setHours(0, 0, 0, 0)
      const dow = bd.getDay()
      bd.setDate(bd.getDate() - (dow + 6) % 7)
      runMergeCheck(pendingSlot, ownSlots, bd)
    }
    setDragState(null)
    setResizeState(null)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dragState, resizeState, pendingSlot, preferredSlots])

  useEffect(() => {
    if (dragState || resizeState) {
      document.addEventListener('mouseup', handleDocumentMouseUp)
      return () => document.removeEventListener('mouseup', handleDocumentMouseUp)
    }
  }, [dragState, resizeState, handleDocumentMouseUp])

  useEffect(() => {
    if (!deletingSlotId) return
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') setDeletingSlotId(null)
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [deletingSlotId])

  // ── Grid event handlers ──────────────────────────────────────────────────

  function handleCellMouseDown(dayIndex: number, _rowIndex: number, cellStartUtc: Date) {
    if (!isEditMode) return
    const startUtc = new Date(cellStartUtc)
    const endUtc = new Date(startUtc)
    endUtc.setMinutes(endUtc.getMinutes() + 30)

    // baseDate is needed by runMergeCheck to resolve dayIndex → calendar date.
    // Derive it from cellStartUtc itself: go back to Monday of the cell's week.
    const baseDate = new Date(cellStartUtc)
    baseDate.setHours(0, 0, 0, 0)
    const dow = baseDate.getDay()
    baseDate.setDate(baseDate.getDate() - (dow + 6) % 7)

    setDragState({ dayIndex, anchorCellStartUtc: startUtc, baseDate })
    setPendingSlot({ dayIndex, startUtc, endUtc })
    setSlotsToDelete([])
    setDisplayedPreferredSlots(preferredSlots as PreferredSlot[])
  }

  function handleCellMouseEnter(dayIndex: number, _rowIndex: number, cellStartUtc: Date) {
    if (!isEditMode) return

    if (dragState) {
      if (dayIndex !== dragState.dayIndex) return

      const anchorStart = dragState.anchorCellStartUtc
      const currentStart = cellStartUtc

      let startUtc: Date
      let endUtc: Date

      if (currentStart >= anchorStart) {
        // Dragging downward
        startUtc = new Date(anchorStart)
        endUtc = new Date(currentStart)
        endUtc.setMinutes(endUtc.getMinutes() + 30)
      } else {
        // Dragging upward
        startUtc = new Date(currentStart)
        endUtc = new Date(anchorStart)
        endUtc.setMinutes(endUtc.getMinutes() + 30)
      }

      setPendingSlot({ dayIndex: dragState.dayIndex, startUtc, endUtc })
      return
    }

    if (resizeState && pendingSlot) {
      const cellStart = new Date(cellStartUtc)
      const cellEnd = new Date(cellStart)
      cellEnd.setMinutes(cellEnd.getMinutes() + 30)

      if (resizeState.edge === 'top') {
        // Move start, clamp so start stays at least 30min before end
        const minStart = new Date(pendingSlot.endUtc)
        minStart.setMinutes(minStart.getMinutes() - 30)
        const newStart = cellStart <= minStart ? cellStart : minStart
        setPendingSlot({ ...pendingSlot, startUtc: newStart })
      } else {
        // Move end, clamp so end stays at least 30min after start
        const maxEnd = new Date(pendingSlot.startUtc)
        maxEnd.setMinutes(maxEnd.getMinutes() + 30)
        const newEnd = cellEnd >= maxEnd ? cellEnd : maxEnd
        setPendingSlot({ ...pendingSlot, endUtc: newEnd })
      }
    }
  }

  function handlePendingSlotEdgeMouseDown(edge: 'top' | 'bottom', e: React.MouseEvent) {
    e.preventDefault()
    setResizeState({ edge })
  }

  // ── Enter / cancel / done ────────────────────────────────────────────────

  function enterEditMode() {
    if (event.status === 'confirmed') return
    setIsEditMode(true)
    setPendingSlot(null)
    setDragState(null)
    setResizeState(null)
    setSlotsToDelete([])
    setDoneError(null)
    setDisplayedPreferredSlots(preferredSlots as PreferredSlot[])
  }

  function cancelEditMode() {
    setIsEditMode(false)
    setPendingSlot(null)
    setDragState(null)
    setResizeState(null)
    setSlotsToDelete([])
    setDoneError(null)
    setDisplayedPreferredSlots(preferredSlots as PreferredSlot[])
  }

  async function handleDone() {
    setIsDonePending(true)
    setDoneError(null)
    try {
      // 1. Delete all slots that were merged/replaced (in parallel)
      const deleteResults = await Promise.allSettled(
        slotsToDelete.map((id) => deletePreferredSlot(id))
      )
      const deleteFailures = deleteResults.filter((r) => r.status === 'rejected')
      if (deleteFailures.length > 0) {
        setDoneError('Failed to save — try again')
        return
      }

      // 2. Save the pending slot if one exists
      if (pendingSlot) {
        await savePreferredSlot({
          start_time_utc: pendingSlot.startUtc.toISOString(),
          end_time_utc: pendingSlot.endUtc.toISOString(),
        })
      }

      // Success — exit edit mode; query invalidation from mutation hooks will refresh the grid
      setIsEditMode(false)
      setPendingSlot(null)
      setDragState(null)
      setResizeState(null)
      setSlotsToDelete([])
    } catch {
      setDoneError('Failed to save — try again')
    } finally {
      setIsDonePending(false)
    }
  }

  const changesCount = slotsToDelete.length + (pendingSlot ? 1 : 0)

  const currentParticipant = event.participants.find((p) => p.user_id === currentUserId)
  const canInvite = isCoordinator || (currentParticipant?.can_invite ?? false)
  const acceptedParticipants = event.participants.filter((p) => p.status === 'accepted')

  function handleCopyLink() {
    try {
      navigator.clipboard.writeText(window.location.href)
      setCopyLabel('Copied!')
      setTimeout(() => setCopyLabel('Copy Link'), 2000)
    } catch {
      window.prompt('Copy this link:', window.location.href)
    }
  }

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Navbar />

      {/* Two-column full-height split — stacked on mobile, side-by-side on md+ */}
      <main className="flex-1 min-h-0 flex flex-col md:flex-row overflow-hidden">

        {/* ── Left: Availability Grid ── */}
        <section className="flex-1 min-h-0 flex flex-col overflow-hidden p-4 md:p-6 lg:p-8 bg-surface">
          <div className="flex flex-col flex-1 gap-4 min-h-0">

            <GridHeader
              isEditMode={isEditMode}
              eventStatus={event.status}
              onEdit={enterEditMode}
              presentUsers={presentUsers}
            />

            {/* Grid — extra bottom padding when action bar is visible */}
            <div className={`flex-1 min-h-0 flex flex-col overflow-hidden ${isEditMode ? 'pb-20' : ''}`}>
              {(() => {
                // Compute the same Monday-anchored column dates the grid uses internally
                const baseDate = toDate(event.earliest_datetime_utc)
                const dow = baseDate.getDay()
                baseDate.setHours(0, 0, 0, 0)
                baseDate.setDate(baseDate.getDate() - (dow + 6) % 7)
                const columnDates = Array.from({ length: 7 }, (_, i) => {
                  const d = new Date(baseDate)
                  d.setDate(d.getDate() + i)
                  return d
                })
                const eventStart = toDate(event.earliest_datetime_utc)
                // Mirror the grid's isScrollable / totalRows calculation so the overlay
                // uses the same coordinate system (px vs % based positioning).
                const earliestDate = toDate(event.earliest_datetime_utc)
                const latestDate = toDate(event.latest_datetime_utc)
                const startHour = earliestDate.getHours()
                const latestHour = latestDate.getHours()
                const latestMinute = latestDate.getMinutes()
                const endHour = latestMinute > 0 ? latestHour + 1 : latestHour
                const totalHours = endHour - startHour
                const gridIsScrollable = totalHours > 8
                const totalRows = totalHours * 2
                return (
                  <AvailabilityGrid
                    key={`${event.earliest_datetime_utc}-${event.latest_datetime_utc}`}
                    segments={segments}
                    preferredSlots={displayedPreferredSlots}
                    startDate={event.earliest_datetime_utc}
                    earliestTime={event.earliest_datetime_utc}
                    latestTime={event.latest_datetime_utc}
                    isEditMode={isEditMode}
                    eventStatus={event.status}
                    pendingSlot={pendingSlot}
                    currentUserId={currentUserId}
                    deletingSlotId={deletingSlotId}
                    slotsToDelete={slotsToDelete}
                    overlayContent={
                      <ProposedTimeOverlay
                        proposals={proposals ?? []}
                        visible={showProposedOverlay}
                        eventStart={eventStart}
                        columnDates={columnDates}
                        isScrollable={gridIsScrollable}
                        totalRows={totalRows}
                      />
                    }
                    onCellMouseDown={handleCellMouseDown}
                    onCellMouseEnter={handleCellMouseEnter}
                    onPendingSlotEdgeMouseDown={handlePendingSlotEdgeMouseDown}
                    onSlotClick={(id) => setDeletingSlotId(id)}
                    onSlotDeleteConfirm={(id) => {
                      setDeletingSlotId(null)
                      if (isEditMode) {
                        setSlotsToDelete((prev) => [...prev, id])
                        setDisplayedPreferredSlots((prev) => prev.filter((s) => s.id !== id))
                      } else {
                        deletePreferredSlot(id)
                      }
                    }}
                    onSlotDeleteCancel={() => setDeletingSlotId(null)}
                  />
                )
              })()}
            </div>
          </div>

          {/* ── Floating action bar — visible while in edit mode ── */}
          {isEditMode && (
            <div className="absolute bottom-0 left-0 right-0 mx-6 lg:mx-8 mb-6 z-20 pointer-events-none">
              <div className="pointer-events-auto bg-surface-container-lowest rounded-xl shadow-[0_8px_32px_-8px_rgba(155,68,40,0.25)] border border-outline-variant/30 px-5 py-3 flex items-center justify-between gap-4">
                <div className="flex flex-col">
                  <span className="text-sm font-bold text-on-surface">
                    {changesCount} {changesCount === 1 ? 'change' : 'changes'} pending
                  </span>
                  {doneError && (
                    <span className="text-xs text-error font-semibold">{doneError}</span>
                  )}
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    onClick={cancelEditMode}
                    className="px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-sm font-bold hover:bg-surface-container transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDone}
                    disabled={isDonePending}
                    className="px-5 py-2 rounded-lg bg-primary text-on-primary text-sm font-bold hover:bg-primary/90 transition-colors disabled:opacity-60"
                  >
                    {isDonePending ? 'Saving…' : 'Done'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </section>

        {/* ── Right: Event Info + Actions ── */}
        <section className="w-full md:w-[400px] shrink-0 lg:w-[456px] xl:w-[504px] md:h-full overflow-y-auto hide-scrollbar bg-surface-container-low p-4 md:p-6 flex flex-col gap-6 md:gap-8 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.03)] z-10">

          {/* ── Section 1: Event Header card ── */}
          <div className="bg-surface-container-lowest p-6 rounded-lg relative shadow-sm">

            {isCoordinator && event.status !== 'confirmed' && (
              <button
                onClick={() => setShowEdit(true)}
                className="absolute top-4 right-4 p-2 hover:bg-surface-container-high rounded-full transition-colors text-outline"
                aria-label="Edit event"
              >
                <Pencil className="w-5 h-5" />
              </button>
            )}

            {/* Type badge + status badge */}
            <div className="flex gap-2 mb-4">
              <span className="px-3 py-1 bg-secondary-container text-on-secondary-container text-[10px] font-bold uppercase tracking-wider rounded-full">
                {typeLabel(event.event_type)}
              </span>
              <StatusBadge status={event.status} />
            </div>

            {/* Event name */}
            <h2 className="text-3xl font-extrabold font-headline text-on-surface mb-2 leading-tight">
              {event.name}
            </h2>

            {/* Date + location rows */}
            <div className="space-y-2 mt-4">
              <div className="flex items-center gap-3 text-on-surface-variant">
                <CalendarDays className="w-5 h-5 text-primary flex-shrink-0" />
                <span className="text-sm font-medium">
                  {formatDateWindowWithYear(event.earliest_datetime_utc, event.latest_datetime_utc)}
                </span>
              </div>
              {event.location && (
                <div className="flex items-center gap-3 text-on-surface-variant">
                  <MapPin className="w-5 h-5 text-primary flex-shrink-0" />
                  <span className="text-sm font-medium">{event.location}</span>
                </div>
              )}
            </div>
          </div>

          {/* ── Section 2: Actions ── */}
          {event.status !== 'confirmed' && (
            <div className="space-y-4">
              <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em] px-1">
                Actions
              </label>

              <button
                onClick={handleViewProposedTimes}
                disabled={isCheckingProposals}
                className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold shadow-[0_15px_30px_-10px_rgba(155,68,40,0.3)] flex items-center justify-center gap-2 transform hover:-translate-y-0.5 transition-all duration-300 disabled:opacity-70 disabled:cursor-not-allowed disabled:hover:translate-y-0"
              >
                {isCheckingProposals ? (
                  <>
                    <RefreshCw className="w-5 h-5 animate-spin" />
                    Updating proposals...
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                      <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
                    </svg>
                    {showProposedOverlay ? 'Hide Proposed Times' : 'View Proposed Times'}
                  </>
                )}
              </button>

              <div className="grid grid-cols-2 gap-3">

                <button
                  onClick={() => syncCalendar()}
                  disabled={isSyncing}
                  className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors disabled:opacity-60"
                >
                  <RefreshCw className={`w-[18px] h-[18px] flex-shrink-0 ${isSyncing ? 'animate-spin' : ''}`} />
                  {isSyncing ? 'Syncing…' : 'Refresh'}
                </button>

                {canInvite ? (
                  <button
                    onClick={() => setShowInvite((v) => !v)}
                    className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors"
                  >
                    <UserPlus className="w-[18px] h-[18px] flex-shrink-0" />
                    Invite
                  </button>
                ) : null}

                <button
                  onClick={handleCopyLink}
                  className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors"
                >
                  <Link2 className="w-[18px] h-[18px] flex-shrink-0" />
                  {copyLabel}
                </button>

                {isCoordinator ? (
                  <button
                    onClick={() => syncAll()}
                    disabled={isSyncingAll}
                    className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors disabled:opacity-60"
                  >
                    <RefreshCcw className={`w-[18px] h-[18px] flex-shrink-0 ${isSyncingAll ? 'animate-spin' : ''}`} />
                    {isSyncingAll ? 'Syncing…' : 'Sync All'}
                  </button>
                ) : null}
              </div>

              {showInvite && (
                <InviteInput
                  uid={event.uid}
                  coordinatorId={event.coordinator_id}
                  currentUserId={currentUserId}
                />
              )}
            </div>
          )}

          {/* RSVP selector */}
          <RsvpSelector uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />

          {/* ── Section 3: Top Proposals ── */}
          {proposalsEnabled && event.status !== 'confirmed' && (
            <ProposalList
              uid={event.uid}
              proposals={proposals ?? []}
              isLoadingProposals={isLoadingProposals}
              isCoordinator={isCoordinator}
              isRefreshing={isRefreshing}
              proposalsStale={proposalsStale}
              proposalsNeedsRegeneration={event.proposals_needs_regeneration ?? false}
              currentUserId={currentUserId}
              onRefresh={() => refreshProposals(undefined, { onSuccess: () => setProposalsStale(false) })}
              onFinalize={() => setShowFinalizeCard(true)}
            />
          )}

          {/* ── Confirmed event banner ── */}
          {event.status === 'confirmed' && event.finalized_start_time_utc && event.finalized_end_time_utc && (
            <div className="bg-primary/8 border border-primary/20 rounded-xl p-4 flex items-start gap-3">
              <CalendarCheck className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="text-xs font-extrabold text-primary uppercase tracking-wider">Scheduled</p>
                <p className="text-sm font-bold text-on-surface">
                  {formatLongDate(event.finalized_start_time_utc)}
                </p>
                <p className="text-xs font-medium text-on-surface-variant">
                  {formatTime(event.finalized_start_time_utc)}
                  {' – '}
                  {formatTime(event.finalized_end_time_utc)}
                </p>
                {event.location && (
                  <p className="text-xs font-medium text-on-surface-variant flex items-center gap-1 pt-0.5">
                    <MapPin className="w-3 h-3 shrink-0" />
                    {event.location}
                  </p>
                )}
                {event.video_call_link && (
                  <a
                    href={event.video_call_link}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs font-medium text-primary flex items-center gap-1 pt-0.5 hover:underline"
                  >
                    <Link2 className="w-3 h-3 shrink-0" />
                    Join video call
                  </a>
                )}
                {event.google_calendar_event_id && (
                  <p className="text-[10px] font-medium text-primary/70 flex items-center gap-1 pt-0.5">
                    <Calendar className="w-3 h-3" />
                    Added to Google Calendar
                  </p>
                )}
              </div>
            </div>
          )}

          {/* ── Section 4: Participants ── */}
          <div className="space-y-4 pb-12">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em] px-1">
              Participants ({event.participants.length})
            </label>
            <div className="space-y-1">
              <ParticipantList
                key={participantsKey}
                uid={event.uid}
                coordinatorId={event.coordinator_id}
                currentUserId={currentUserId}
              />
            </div>
          </div>

          {/* Delete event — coordinator only */}
          {isCoordinator && (
            <div className="pb-4 -mt-4">
              <button
                onClick={() => setShowDelete(true)}
                className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-error-container/60 border border-error/20 text-on-error-container text-xs font-bold hover:bg-error-container transition-colors"
              >
                <Trash2 className="w-3.5 h-3.5" />
                Delete Event
              </button>
            </div>
          )}
        </section>
      </main>

      {/* Modals */}
      {showEdit && <EditModal event={event} onClose={() => setShowEdit(false)} onSave={handleSave} />}
      {showDelete && <DeleteModal event={event} onClose={() => setShowDelete(false)} />}
      {showFinalizeCard && (
        <FinalizeCard
          event={event}
          proposals={proposals ?? []}
          acceptedParticipants={acceptedParticipants}
          onClose={() => setShowFinalizeCard(false)}
          onSuccess={() => {
            setShowFinalizeCard(false)
            queryClient.invalidateQueries({ queryKey: ['events', event.uid] })
          }}
        />
      )}
    </div>
  )
}
