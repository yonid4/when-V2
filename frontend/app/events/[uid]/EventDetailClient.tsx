'use client'

import { useState, useEffect, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import {
  MapPin,
  Trash2,
  Pencil,
  X,
  Check,
  CalendarDays,
  RefreshCw,
  UserPlus,
  Link2,
  RefreshCcw,
  Calendar,
} from 'lucide-react'
import { useQueryClient } from '@tanstack/react-query'
import { useUpdateEvent, useDeleteEvent } from '@/hooks/useEvent'
import { useEventBusySlots, useSyncCalendar, useSyncMyCalendar } from '@/hooks/useBusySlots'
import { usePreferredSlots, useSavePreferredSlot, useDeletePreferredSlot } from '@/hooks/usePreferredSlots'
import { useProposals, useRefreshProposals } from '@/hooks/useProposals'
import { supabase } from '@/lib/supabase'
import { ParticipantList } from '@/components/event/ParticipantList'
import { InviteInput } from '@/components/event/InviteInput'
import { RsvpSelector } from '@/components/event/RsvpSelector'
import { Navbar } from '@/components/layout/Navbar'
import { useAuthStore } from '@/stores/authStore'
import type { BusySlot, EventWithParticipants, EventType, PreferredSlot, ProposalResponse } from '@/types'
import type { SlotLike } from '@/lib/gridUtils'
import { computeMerge } from '@/lib/editModeUtils'
import type { PendingSlot } from '@/lib/editModeUtils'
import {
  editSchema,
  toDatetimeLocal,
  computeEditDiff,
} from './editEventUtils'
import type { EditValues, EditSaveResult } from './editEventUtils'

// ─── Edit modal ──────────────────────────────────────────────────────────────

function EditModal({
  event,
  onClose,
  onSave,
}: {
  event: EventWithParticipants
  onClose: () => void
  onSave: (result: EditSaveResult) => void
}) {
  const { mutate: updateEvent, isPending } = useUpdateEvent(event.uid)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: event.name,
      allow_guest_invites: event.allow_guest_invites ?? false,
      earliest_local: toDatetimeLocal(event.earliest_datetime_utc),
      latest_local: toDatetimeLocal(event.latest_datetime_utc),
      event_type: event.event_type,
      duration_minutes: event.duration_minutes,
      description: event.description ?? '',
      location: event.location ?? '',
      video_call_link: event.video_call_link ?? '',
    },
  })

  function onSubmit(data: EditValues) {
    if (data.latest_local <= data.earliest_local) {
      setError('latest_local', { message: 'Latest time must be after earliest time' })
      return
    }

    const diff = computeEditDiff(data, event)

    updateEvent(diff.updated, {
      onSuccess: () => {
        onSave(diff)
        onClose()
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-2xl shadow-warm-md">
        <div className="flex items-center justify-between p-6 border-b border-outline-variant/20">
          <h2 className="text-xl font-bold text-on-surface">Edit Event</h2>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-surface-container transition-colors">
            <X className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
          {/* Event Name */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Event Name</label>
            <input
              {...register('name')}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
            />
            {errors.name && <p className="text-sm text-error">{errors.name.message}</p>}
          </div>

          {/* Allow guest invites */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <div>
                <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Allow guests to invite others</label>
                <p className="text-xs text-on-surface-variant/70 mt-0.5">When enabled, all participants can invite new people</p>
              </div>
              <label className="relative inline-flex items-center cursor-pointer ml-4 shrink-0">
                <input
                  {...register('allow_guest_invites')}
                  type="checkbox"
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-surface-container-high peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-primary-fixed rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
              </label>
            </div>
          </div>

          {/* Event Time Range */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">
              Event Time Range <span className="normal-case font-normal text-on-surface-variant/60">(Times shown in your local timezone)</span>
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-[10px] font-semibold text-on-surface-variant/70 uppercase tracking-wider">Earliest Time</label>
                <input
                  {...register('earliest_local')}
                  type="datetime-local"
                  className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
                />
                {errors.earliest_local && <p className="text-sm text-error">{errors.earliest_local.message}</p>}
              </div>
              <div className="space-y-1">
                <label className="text-[10px] font-semibold text-on-surface-variant/70 uppercase tracking-wider">Latest Time</label>
                <input
                  {...register('latest_local')}
                  type="datetime-local"
                  className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
                />
                {errors.latest_local && <p className="text-sm text-error">{errors.latest_local.message}</p>}
              </div>
            </div>
          </div>

          {/* Event Type */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Event Type</label>
            <select
              {...register('event_type')}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
            >
              <option value="meeting">Meeting</option>
              <option value="social">Social</option>
              <option value="birthday">Birthday</option>
              <option value="other">Other</option>
            </select>
            {errors.event_type && <p className="text-sm text-error">{errors.event_type.message}</p>}
          </div>

          {/* Duration */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Duration (minutes)</label>
            <input
              {...register('duration_minutes', { valueAsNumber: true })}
              type="number"
              min={15}
              step={15}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
            />
            <p className="text-xs text-on-surface-variant/70">Minimum 15 minutes</p>
            {errors.duration_minutes && <p className="text-sm text-error">{errors.duration_minutes.message}</p>}
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Description</label>
            <textarea
              {...register('description')}
              rows={3}
              placeholder="Describe your event..."
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all resize-none placeholder:text-outline/50"
            />
          </div>

          {/* Location */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Location</label>
            <input
              {...register('location')}
              placeholder="Conference Room A, 123 Main St..."
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50"
            />
          </div>

          {/* Video Call Link */}
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Video Call Link</label>
            <input
              {...register('video_call_link')}
              type="url"
              placeholder="https://meet.google.com/..."
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50"
            />
            {errors.video_call_link && <p className="text-sm text-error">{errors.video_call_link.message}</p>}
          </div>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold hover:bg-surface-container transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className="flex-1 py-3 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold flex items-center justify-center gap-2 disabled:opacity-60"
            >
              <Check className="w-4 h-4" />
              {isPending ? 'Saving…' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ─── Delete modal ────────────────────────────────────────────────────────────

function DeleteModal({
  event,
  onClose,
}: {
  event: EventWithParticipants
  onClose: () => void
}) {
  const router = useRouter()
  const { mutate: deleteEvent, isPending } = useDeleteEvent()

  function handleDelete() {
    deleteEvent(event.uid, {
      onSuccess: () => router.push('/dashboard'),
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-md shadow-warm-md">
        <div className="p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-error-container flex items-center justify-center mx-auto">
            <Trash2 className="w-6 h-6 text-on-error-container" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-on-surface">Delete Event</h2>
            <p className="text-sm text-on-surface-variant mt-2">
              Are you sure you want to delete{' '}
              <span className="font-semibold text-on-surface">"{event.name}"</span>? All participants
              will be notified. This action cannot be undone.
            </p>
          </div>
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold hover:bg-surface-container transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isPending}
              className="flex-1 py-3 rounded-xl bg-error text-on-error font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:-translate-y-0.5 transition-all duration-300"
            >
              <Trash2 className="w-4 h-4" />
              {isPending ? 'Deleting…' : 'Delete Event'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Availability grid ────────────────────────────────────────────────────────

function busyIntensityClass(count: number): string {
  if (count >= 7) return 'bg-error/90'
  if (count >= 5) return 'bg-error/65'
  if (count >= 3) return 'bg-error/40'
  return 'bg-error/20'
}

function preferredIntensityClass(count: number): string {
  if (count >= 7) return 'bg-secondary/90'
  if (count >= 5) return 'bg-secondary/65'
  if (count >= 3) return 'bg-secondary/40'
  return 'bg-secondary/20'
}

function formatSlotTime(utcString: string): string {
  const d = new Date(utcString)
  return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

interface SlotOverlay {
  startUtc: Date
  endUtc: Date
  /** unique participants involved (for intensity) */
  count: number
}

interface ConflictOverlay {
  startUtc: Date
  endUtc: Date
  busyCount: number
  preferredCount: number
}

/** Group continuous/overlapping slots of the same type into merged overlay blocks. */
function mergeSlots(slots: SlotLike[]): SlotOverlay[] {
  if (slots.length === 0) return []
  // Sort by start
  const sorted = [...slots].sort(
    (a, b) => new Date(a.start_time_utc).getTime() - new Date(b.start_time_utc).getTime(),
  )
  const result: SlotOverlay[] = []
  let curStart = new Date(sorted[0].start_time_utc)
  let curEnd = new Date(sorted[0].end_time_utc)
  let curCount = 1

  for (let i = 1; i < sorted.length; i++) {
    const s = new Date(sorted[i].start_time_utc)
    const e = new Date(sorted[i].end_time_utc)
    if (s <= curEnd) {
      // overlapping or adjacent — extend
      if (e > curEnd) curEnd = e
      curCount++
    } else {
      result.push({ startUtc: curStart, endUtc: curEnd, count: curCount })
      curStart = s
      curEnd = e
      curCount = 1
    }
  }
  result.push({ startUtc: curStart, endUtc: curEnd, count: curCount })
  return result
}

/** Build conflict overlays: only the intersection where busy and preferred overlap. */
function buildConflictOverlays(
  busyOverlays: SlotOverlay[],
  preferredOverlays: SlotOverlay[],
): ConflictOverlay[] {
  const conflicts: ConflictOverlay[] = []
  for (const b of busyOverlays) {
    for (const p of preferredOverlays) {
      const overlapStart = b.startUtc > p.startUtc ? b.startUtc : p.startUtc
      const overlapEnd = b.endUtc < p.endUtc ? b.endUtc : p.endUtc
      if (overlapStart < overlapEnd) {
        conflicts.push({ startUtc: overlapStart, endUtc: overlapEnd, busyCount: b.count, preferredCount: p.count })
      }
    }
  }
  return conflicts
}

/** Return the portions of overlay NOT covered by any conflict. */
function subtractConflicts(
  overlay: SlotOverlay,
  conflicts: ConflictOverlay[],
): Array<{ startUtc: Date; endUtc: Date }> {
  let segments: Array<{ startUtc: Date; endUtc: Date }> = [
    { startUtc: overlay.startUtc, endUtc: overlay.endUtc },
  ]
  for (const conflict of conflicts) {
    const next: Array<{ startUtc: Date; endUtc: Date }> = []
    for (const seg of segments) {
      if (seg.startUtc < conflict.startUtc) {
        next.push({ startUtc: seg.startUtc, endUtc: conflict.startUtc < seg.endUtc ? conflict.startUtc : seg.endUtc })
      }
      if (seg.endUtc > conflict.endUtc) {
        next.push({ startUtc: conflict.endUtc > seg.startUtc ? conflict.endUtc : seg.startUtc, endUtc: seg.endUtc })
      }
    }
    segments = next
  }
  return segments.filter((s) => s.endUtc > s.startUtc)
}

/**
 * Break a list of slots into non-overlapping segments with accurate per-segment
 * participant counts. Each boundary point (slot start/end) becomes a segment
 * boundary, and each segment's count = number of input slots that cover it.
 */
function buildCountedSegments(slots: SlotLike[]): SlotOverlay[] {
  if (slots.length === 0) return []
  // Collect all unique boundary timestamps
  const points = Array.from(
    new Set(slots.flatMap((s) => [new Date(s.start_time_utc).getTime(), new Date(s.end_time_utc).getTime()]))
  ).sort((a, b) => a - b)

  const raw: SlotOverlay[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const segStart = new Date(points[i])
    const segEnd = new Date(points[i + 1])
    const count = slots.filter((s) => {
      const ss = new Date(s.start_time_utc).getTime()
      const se = new Date(s.end_time_utc).getTime()
      return ss <= points[i] && se >= points[i + 1]
    }).length
    if (count > 0) raw.push({ startUtc: segStart, endUtc: segEnd, count })
  }

  // Merge adjacent segments with the same count into one block
  if (raw.length === 0) return []
  const result: SlotOverlay[] = [{ ...raw[0] }]
  for (let i = 1; i < raw.length; i++) {
    const last = result[result.length - 1]
    if (preferredIntensityClass(raw[i].count) === preferredIntensityClass(last.count) && raw[i].startUtc.getTime() === last.endUtc.getTime()) {
      last.endUtc = raw[i].endUtc
      if (raw[i].count > last.count) last.count = raw[i].count
    } else {
      result.push({ ...raw[i] })
    }
  }
  return result
}

/** Clip a slot's start/end to the grid's visible time bounds for a given column. */
function clipToGridBounds(
  startUtc: Date,
  endUtc: Date,
  gridStartUtc: Date,
  gridEndUtc: Date,
): { startUtc: Date; endUtc: Date } {
  return {
    startUtc: startUtc < gridStartUtc ? gridStartUtc : startUtc,
    endUtc: endUtc > gridEndUtc ? gridEndUtc : endUtc,
  }
}

function AvailabilityGrid({
  busySlots,
  preferredSlots,
  startDate,
  earliestTime,
  latestTime,
  isEditMode,
  pendingSlot,
  currentUserId,
  deletingSlotId,
  slotsToDelete,
  onCellMouseDown,
  onCellMouseEnter,
  onPendingSlotEdgeMouseDown,
  onSlotClick,
  onSlotDeleteConfirm,
  onSlotDeleteCancel,
}: {
  busySlots: SlotLike[]
  preferredSlots: SlotLike[]
  startDate: string
  earliestTime: string
  latestTime: string
  isEditMode: boolean
  pendingSlot: PendingSlot | null
  currentUserId: string
  deletingSlotId: string | null
  slotsToDelete: string[]
  onCellMouseDown: (dayIndex: number, rowIndex: number, cellStartUtc: Date) => void
  onCellMouseEnter: (dayIndex: number, rowIndex: number, cellStartUtc: Date) => void
  onPendingSlotEdgeMouseDown: (edge: 'top' | 'bottom', e: React.MouseEvent) => void
  onSlotClick: (slotId: string) => void
  onSlotDeleteConfirm: (slotId: string) => void
  onSlotDeleteCancel: () => void
}) {
  const earliestDate = new Date(earliestTime)
  const latestDate = new Date(latestTime)
  const startHour = earliestDate.getHours()
  const latestHour = latestDate.getHours()
  const latestMinute = latestDate.getMinutes()
  const endHour = latestMinute > 0 ? latestHour + 1 : latestHour
  const totalHours = endHour - startHour

  const hours = Array.from({ length: totalHours }, (_, i) => {
    const h = startHour + i
    const period = h < 12 ? 'AM' : 'PM'
    const display = h % 12 === 0 ? 12 : h % 12
    return `${String(display).padStart(2, '0')}:00 ${period}`
  })

  const isScrollable = totalHours > 8
  const DAY_NAMES = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

  const [weekOffset, setWeekOffset] = useState(0)

  const baseDate = new Date(startDate)
  const dayOfWeek = baseDate.getDay()
  const offsetToMonday = (dayOfWeek + 6) % 7
  baseDate.setDate(baseDate.getDate() - offsetToMonday + weekOffset * 7)

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(baseDate)
    d.setDate(d.getDate() + i)
    return {
      label: DAY_NAMES[d.getDay()],
      date: d.getDate(),
      month: d.toLocaleString('en-US', { month: 'short' }),
      year: d.getFullYear(),
    }
  })

  const firstDay = days[0]
  const lastDay = days[6]
  const monthLabel = firstDay.month === lastDay.month
    ? `${firstDay.month} ${firstDay.year}`
    : `${firstDay.month} – ${lastDay.month} ${lastDay.year}`

  // Total half-rows per day column
  const totalRows = totalHours * 2

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-surface-container-lowest rounded-xl shadow-[0_20px_40px_-15px_rgba(155,68,40,0.05)]">
      {/* Grid card header: week nav + edit button */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 shrink-0">
        <button
          onClick={() => setWeekOffset((o) => o - 1)}
          className="p-1.5 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant"
          aria-label="Previous week"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">{monthLabel}</span>

        <div className="flex items-center gap-2">
          {isEditMode ? (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-primary/30 bg-primary/5">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-xs font-bold text-primary">Editing…</span>
            </div>
          ) : (
            <button
              data-testid="edit-availability-btn"
              onClick={() => {
                // Signal handled by parent via onCellMouseDown dummy; edit toggle is in parent
              }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-bold hover:bg-surface-container transition-colors"
            >
              <Pencil className="w-3.5 h-3.5" />
              Edit Availability
            </button>
          )}
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="p-1.5 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant"
            aria-label="Next week"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-[80px_1fr] border-b border-outline-variant/25 shrink-0 mx-6">
        <div className="h-12 border-r border-outline-variant/25" />
        <div className="grid grid-cols-7 h-12">
          {days.map((d, i) => (
            <div
              key={i}
              className={`flex items-center justify-center font-bold text-on-surface-variant/80 uppercase text-[10px] tracking-widest ${i < 6 ? 'border-r border-outline-variant/25' : ''}`}
            >
              {d.label} {d.date}
            </div>
          ))}
        </div>
      </div>

      {/* Grid body */}
      <div className={`flex flex-col flex-1 min-h-0 mx-6 mb-6 ${isScrollable ? 'overflow-y-auto' : 'overflow-hidden'}`}>
        <div className={`flex flex-row ${isScrollable ? '' : 'flex-1 min-h-0'}`}>
          {/* Time labels */}
          <div className="w-[80px] shrink-0 flex flex-col">
            {hours.map((h) => (
              <div key={h} className={`flex items-start justify-center pt-1 ${isScrollable ? 'h-16' : 'flex-1'}`}>
                <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-widest">{h}</span>
              </div>
            ))}
          </div>

          {/* Grid cells */}
          <div className={`flex-1 flex flex-col ${isScrollable ? '' : 'min-h-0'}`}>
            <div className={`grid grid-cols-7 ${isScrollable ? '' : 'flex-1 min-h-0'}`}>
              {days.map((_day, di) => {
                const colDate = new Date(baseDate)
                colDate.setDate(colDate.getDate() + di)

                // ── Overlay geometry helper ──────────────────────────────────
                const ROW_HEIGHT_PX = 32 // h-8 when scrollable
                function overlayStyle(slotStartUtc: Date, slotEndUtc: Date): React.CSSProperties {
                  const startMinutes = (slotStartUtc.getHours() - startHour) * 60 + slotStartUtc.getMinutes()
                  const endMinutes = (slotEndUtc.getHours() - startHour) * 60 + slotEndUtc.getMinutes()
                  const startRow = startMinutes / 30
                  const rowsSpanned = (endMinutes - startMinutes) / 30
                  if (isScrollable) {
                    return { position: 'absolute', left: 0, right: 0, pointerEvents: 'none', top: startRow * ROW_HEIGHT_PX + 2, height: rowsSpanned * ROW_HEIGHT_PX - 4 }
                  }
                  const topPct = (startRow / totalRows) * 100
                  const heightPct = (rowsSpanned / totalRows) * 100
                  return { position: 'absolute', left: 0, right: 0, pointerEvents: 'none', top: `calc(${topPct}% + 2px)`, height: `calc(${heightPct}% - 4px)` }
                }

                // ── Slot overlays for this column ────────────────────────────
                const colDayStart = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), startHour, 0)
                const colDayEnd = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), endHour, 0)

                const colBusy = busySlots.filter((s) => {
                  const ss = new Date(s.start_time_utc); const se = new Date(s.end_time_utc)
                  return ss < colDayEnd && se > colDayStart
                })
                const colPreferred = preferredSlots.filter((s) => {
                  const ss = new Date(s.start_time_utc); const se = new Date(s.end_time_utc)
                  return ss < colDayEnd && se > colDayStart
                })

                const busyOverlays = mergeSlots(colBusy)
                // Build per-segment preferred overlays with accurate per-region counts
                const preferredOverlays = buildCountedSegments(colPreferred)
                // For conflict detection, merge preferred into single blocks (as before)
                const preferredMerged = mergeSlots(colPreferred)
                const conflictOverlays = buildConflictOverlays(busyOverlays, preferredMerged)


                // ── Pending slot overlay ─────────────────────────────────────
                const colPending = pendingSlot !== null && pendingSlot.dayIndex === di ? pendingSlot : null
                const pendingOverlayStyle = colPending ? overlayStyle(colPending.startUtc, colPending.endUtc) : null

                return (
                  <div
                    key={di}
                    className={`flex flex-col relative ${isScrollable ? '' : 'flex-1'} ${di < 6 ? 'border-r border-outline-variant/25' : ''}`}
                    onClick={() => { if (deletingSlotId) onSlotDeleteCancel() }}
                  >
                    {Array.from({ length: totalHours }, (_, hi) => {
                      const hour = startHour + hi
                      return [0, 1].map((half) => {
                        const rowIndex = hi * 2 + half
                        const cellStartUtc = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), hour, half === 0 ? 0 : 30)
                        const halfClass = isScrollable ? 'h-8' : 'flex-1'

                        return (
                          <div
                            key={`${hi}-${half}`}
                            className={`border-b border-outline-variant/20 transition-colors ${halfClass} ${
                              isEditMode
                                ? 'cursor-crosshair hover:bg-secondary/10'
                                : 'hover:bg-surface-container-high cursor-pointer'
                            }`}
                            onMouseDown={isEditMode ? () => onCellMouseDown(di, rowIndex, cellStartUtc) : undefined}
                            onMouseEnter={isEditMode ? () => onCellMouseEnter(di, rowIndex, cellStartUtc) : undefined}
                          />
                        )
                      })
                    })}

                    {/* Conflict overlays (rendered first so busy/preferred don't cover them) */}
                    {conflictOverlays.map((c, ci) => {
                      const cc = clipToGridBounds(c.startUtc, c.endUtc, colDayStart, colDayEnd)
                      if (cc.endUtc <= cc.startUtc) return null
                      return (
                        <div
                          key={`conflict-${ci}`}
                          style={overlayStyle(cc.startUtc, cc.endUtc)}
                          className="rounded-md z-20 overflow-hidden relative"
                        >
                          <div className="flex w-full h-full">
                            <div className={`w-1/2 h-full ${busyIntensityClass(c.busyCount)}`} />
                            <div className={`w-1/2 h-full ${preferredIntensityClass(c.preferredCount)}`} />
                            <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
                              <span className="text-xs font-semibold text-error">CONFLICT</span>
                              <span className="text-xs text-gray-600">{formatSlotTime(cc.startUtc.toISOString())} – {formatSlotTime(cc.endUtc.toISOString())}</span>
                            </div>
                          </div>
                        </div>
                      )
                    })}

                    {/* Busy overlays — clipped to non-conflict segments */}
                    {busyOverlays.flatMap((o, oi) =>
                      subtractConflicts(o, conflictOverlays).map((seg, si) => {
                        const cs = clipToGridBounds(seg.startUtc, seg.endUtc, colDayStart, colDayEnd)
                        if (cs.endUtc <= cs.startUtc) return null
                        return (
                          <div
                            key={`busy-${oi}-${si}`}
                            style={overlayStyle(cs.startUtc, cs.endUtc)}
                            className={`${busyIntensityClass(o.count)} rounded-md z-10 overflow-hidden flex items-center justify-center`}
                          >
                            {cs.endUtc.getTime() - cs.startUtc.getTime() >= 30 * 60 * 1000 && (
                              <span className="text-xs text-error font-medium">{formatSlotTime(cs.startUtc.toISOString())} – {formatSlotTime(cs.endUtc.toISOString())}</span>
                            )}
                          </div>
                        )
                      })
                    )}

                    {/* Preferred overlays — clipped to non-conflict segments (display only) */}
                    {preferredOverlays.flatMap((o, oi) =>
                      subtractConflicts(o, conflictOverlays).map((seg, si) => {
                        const cs = clipToGridBounds(seg.startUtc, seg.endUtc, colDayStart, colDayEnd)
                        if (cs.endUtc <= cs.startUtc) return null
                        return (
                          <div
                            key={`preferred-${oi}-${si}`}
                            style={overlayStyle(cs.startUtc, cs.endUtc)}
                            className={`${preferredIntensityClass(o.count)} rounded-md z-10 overflow-hidden flex items-center justify-center`}
                          >
                            {cs.endUtc.getTime() - cs.startUtc.getTime() >= 30 * 60 * 1000 && (
                              <span className="text-xs text-secondary font-medium">{formatSlotTime(cs.startUtc.toISOString())} – {formatSlotTime(cs.endUtc.toISOString())}</span>
                            )}
                          </div>
                        )
                      })
                    )}

                    {/* Own slot dot indicators — one per own preferred slot */}
                    {colPreferred
                      .filter((slot) => (slot as PreferredSlot).user_id === currentUserId && !slotsToDelete.includes((slot as PreferredSlot).id))
                      .map((slot) => {
                        const s = slot as PreferredSlot
                        const clipped = clipToGridBounds(new Date(s.start_time_utc), new Date(s.end_time_utc), colDayStart, colDayEnd)
                        if (clipped.endUtc <= clipped.startUtc) return null
                        return (
                          <div
                            key={`own-dot-${s.id}`}
                            style={{ ...overlayStyle(clipped.startUtc, clipped.endUtc), pointerEvents: 'none', zIndex: 15 }}
                            className="relative"
                          >
                            <div className="absolute bg-secondary rounded-full" style={{ top: 4, right: 6, width: 8, height: 8 }} />
                          </div>
                        )
                      })
                    }

                    {/* Own preferred slot click/delete overlays — only in edit mode */}
                    {isEditMode && colPreferred
                      .filter((slot) => {
                        const s = slot as PreferredSlot
                        return s.user_id === currentUserId && !slotsToDelete.includes(s.id)
                      })
                      .map((slot) => {
                        const s = slot as PreferredSlot
                        const isConfirming = deletingSlotId === s.id
                        const clipped = clipToGridBounds(new Date(s.start_time_utc), new Date(s.end_time_utc), colDayStart, colDayEnd)
                        if (clipped.endUtc <= clipped.startUtc) return null
                        const slotStart = clipped.startUtc
                        const slotEnd = clipped.endUtc
                        return (
                          <div
                            key={`own-preferred-${s.id}`}
                            style={{ ...overlayStyle(slotStart, slotEnd), pointerEvents: 'auto', zIndex: 25 }}
                            className="rounded-md cursor-pointer relative flex items-center justify-center"
                            onClick={(e) => { e.stopPropagation(); onSlotClick(s.id) }}
                          >
                            {isConfirming && (
                              <div
                                className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-surface-container-lowest/95 rounded-md z-30 px-1"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <span className="text-[10px] font-bold text-on-surface text-center leading-tight">Remove this slot?</span>
                                <div className="flex gap-1">
                                  <button
                                    className="px-2 py-0.5 rounded text-[10px] font-bold border border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors"
                                    onClick={(e) => { e.stopPropagation(); onSlotDeleteCancel() }}
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    className="px-2 py-0.5 rounded text-[10px] font-bold bg-error text-on-error hover:bg-error/90 transition-colors"
                                    onClick={(e) => { e.stopPropagation(); onSlotDeleteConfirm(s.id) }}
                                  >
                                    Remove
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })
                    }

                    {/* Pending slot overlay */}
                    {pendingOverlayStyle && (
                      <div
                        style={{ ...pendingOverlayStyle, pointerEvents: 'none' }}
                        className="border-2 border-dashed border-secondary bg-secondary/20 rounded-md z-10"
                      >
                        <div
                          style={{ pointerEvents: 'auto' }}
                          className="absolute top-0 left-0 right-0 h-2 cursor-ns-resize"
                          onMouseDown={(e) => { e.stopPropagation(); onPendingSlotEdgeMouseDown('top', e) }}
                        />
                        <div
                          style={{ pointerEvents: 'auto' }}
                          className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize"
                          onMouseDown={(e) => { e.stopPropagation(); onPendingSlotEdgeMouseDown('bottom', e) }}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Helpers ──────────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: 'bg-secondary-container text-on-secondary-container',
    planning: 'bg-surface-container-high text-on-surface-variant',
    cancelled: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full ${styles[status] ?? styles.planning}`}>
      {status}
    </span>
  )
}

function typeLabel(t: EventType) {
  return t.charAt(0).toUpperCase() + t.slice(1).replace('_', ' ')
}

function formatDateWindow(earliest: string, latest: string) {
  const fmt = (d: string) =>
    new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(earliest)} – ${fmt(latest)}`
}

// ─── Main export ─────────────────────────────────────────────────────────────

export default function EventDetailClient({
  event: initialEvent,
}: {
  event: EventWithParticipants
}) {
  const { user } = useAuthStore()
  const currentUserId = user?.id ?? ''

  const [event, setEvent] = useState(initialEvent)
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
  const [proposalsStale, setProposalsStale] = useState(false)

  function handleSave(result: EditSaveResult) {
    if (result.infoChanged || result.timeRangeChanged) {
      setEvent((prev) => ({ ...prev, ...result.updated }))
    }
    if (result.guestInvitesChanged) {
      setParticipantsKey((k) => k + 1)
    }
  }

  const queryClient = useQueryClient()
  const { data: busySlots = [] } = useEventBusySlots(event.uid)
  const { data: preferredSlots = [] } = usePreferredSlots(event.uid)
  const { mutate: syncCalendar, isPending: isSyncing } = useSyncMyCalendar()
  const { mutateAsync: savePreferredSlot } = useSavePreferredSlot(event.uid)
  const { mutateAsync: deletePreferredSlot } = useDeletePreferredSlot(event.uid)

  // Keep displayed preferred slots in sync with fetched data (when not in edit mode)
  useEffect(() => {
    if (!isEditMode) {
      setDisplayedPreferredSlots(preferredSlots as PreferredSlot[])
    }
  }, [preferredSlots, isEditMode])

  // Real-time subscription: invalidate preferred slots on INSERT or DELETE
  useEffect(() => {
    if (!event.id) return
    const channel = supabase
      .channel(`preferred-slots-${event.id}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${event.id}` },
        () => {
          queryClient.invalidateQueries({ queryKey: ['preferred-slots', event.uid] })
          setProposalsStale(true)
        }
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${event.id}` },
        () => {
          queryClient.invalidateQueries({ queryKey: ['preferred-slots', event.uid] })
          setProposalsStale(true)
        }
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [event.id, event.uid, queryClient])

  const { mutate: syncAll, isPending: isSyncingAll } = useSyncCalendar(event.uid)

  const { data: proposals, isLoading: isLoadingProposals } = useProposals(event.uid, proposalsEnabled)
  const { mutate: refreshProposals, isPending: isRefreshing } = useRefreshProposals(event.uid)

  function runMergeCheck(
    pending: PendingSlot,
    allConfirmedSlots: PreferredSlot[],
    weekBaseDate: Date
  ) {
    const result = computeMerge(
      pending,
      allConfirmedSlots,
      (slot) => {
        const slotDate = new Date(slot.start_time_utc)
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

      {/* Two-column full-height split */}
      <main className="flex-1 min-h-0 flex flex-row overflow-hidden">

        {/* ── Left: Availability Grid ── */}
        <section className="flex-1 min-h-0 flex flex-col overflow-hidden p-6 lg:p-8 bg-surface">
          <div className="flex flex-col flex-1 gap-4 min-h-0">

            {/* Grid header */}
            <div className="flex flex-col gap-4">
              <div className="flex items-center justify-between">
                <h2 className="text-3xl font-extrabold font-headline text-primary tracking-tight">
                  Availability Grid
                </h2>
                {/* Legend */}
                <div className="flex flex-wrap gap-4 text-[10px] sm:text-xs font-bold uppercase tracking-wider">
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-error" />
                    Busy
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-secondary" />
                    Preferred
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="w-3 h-3 rounded-full bg-primary-container/40" />
                    Proposed
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-3 h-3 rounded-full overflow-hidden flex border border-error/10">
                      <div className="w-1/2 h-full bg-error" />
                      <div className="w-1/2 h-full bg-secondary" />
                    </div>
                    Conflict
                  </div>
                </div>
              </div>

              {/* Heatmap intensity legend */}
              <div className="flex items-center gap-3 bg-surface-container-low px-3 py-2 rounded-lg w-fit ml-auto">
                <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-tighter">
                  Intensity (Heatmap)
                </span>
                <div className="flex items-center gap-1">
                  <div className="w-2.5 h-2.5 rounded-sm bg-error/20" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-error/40" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-error/70" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-error" />
                </div>
                <div className="flex items-center gap-1 ml-1">
                  <div className="w-2.5 h-2.5 rounded-sm bg-secondary/20" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-secondary/40" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-secondary/70" />
                  <div className="w-2.5 h-2.5 rounded-sm bg-secondary" />
                </div>
                <span className="text-[10px] font-bold text-on-surface-variant/40 ml-1">+ People</span>
              </div>
            </div>

            {/* Edit availability button — sits above grid card when not in edit mode */}
            {!isEditMode && (
              <div className="flex justify-end">
                <button
                  data-testid="edit-availability-btn"
                  onClick={enterEditMode}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-bold hover:bg-surface-container transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Edit Availability
                </button>
              </div>
            )}

            {/* Grid — extra bottom padding when action bar is visible */}
            <div className={`flex-1 min-h-0 flex flex-col overflow-hidden ${isEditMode ? 'pb-20' : ''}`}>
              <AvailabilityGrid
                busySlots={busySlots}
                preferredSlots={displayedPreferredSlots}
                startDate={event.earliest_datetime_utc}
                earliestTime={event.earliest_datetime_utc}
                latestTime={event.latest_datetime_utc}
                isEditMode={isEditMode}
                pendingSlot={pendingSlot}
                currentUserId={currentUserId}
                deletingSlotId={deletingSlotId}
                slotsToDelete={slotsToDelete}
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
        <section className="w-full md:w-[456px] shrink-0 lg:w-[504px] xl:w-[552px] h-full overflow-y-auto hide-scrollbar bg-surface-container-low p-6 flex flex-col gap-8 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.03)] z-10">

          {/* ── Section 1: Event Header card ── */}
          <div className="bg-surface-container-lowest p-6 rounded-lg relative shadow-sm">

            {isCoordinator && (
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
                  {formatDateWindow(event.earliest_datetime_utc, event.latest_datetime_utc)}
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
          <div className="space-y-4">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em] px-1">
              Actions
            </label>

            <button
              onClick={() => setProposalsEnabled(true)}
              className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold shadow-[0_15px_30px_-10px_rgba(155,68,40,0.3)] flex items-center justify-center gap-2 transform hover:-translate-y-0.5 transition-all duration-300"
            >
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
              </svg>
              View Proposed Times
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

          {/* RSVP selector */}
          <RsvpSelector uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />

          {/* ── Section 3: Top Proposals ── */}
          {proposalsEnabled && (
            <div className="space-y-4">
              <div className="flex items-center justify-between px-1">
                <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
                  Top Proposals
                </label>
                {isCoordinator && (
                  <button
                    onClick={() => refreshProposals(undefined, { onSuccess: () => setProposalsStale(false) })}
                    disabled={isRefreshing}
                    className="flex items-center gap-1 text-[10px] font-bold text-primary uppercase tracking-wider hover:text-primary/70 transition-colors disabled:opacity-50"
                  >
                    <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
                    {isRefreshing ? 'Regenerating…' : 'Regenerate'}
                  </button>
                )}
              </div>

              {/* Stale banner */}
              {(proposalsStale || event.proposals_needs_regeneration) && (
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-tertiary-container/40 border border-tertiary/20">
                  <RefreshCw className="w-3.5 h-3.5 text-on-tertiary-container flex-shrink-0" />
                  <p className="text-xs font-medium text-on-tertiary-container">
                    Availability changed — proposals may be outdated.
                  </p>
                </div>
              )}

              {isLoadingProposals && (
                <div className="flex items-center justify-center py-8">
                  <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                </div>
              )}

              {!isLoadingProposals && proposals && proposals.length === 0 && (
                <div className="bg-surface-container-lowest p-4 rounded-xl flex items-center gap-4 shadow-sm">
                  <div className="h-10 w-10 bg-surface-container-low rounded-lg flex items-center justify-center text-primary flex-shrink-0">
                    <Calendar className="w-5 h-5" />
                  </div>
                  <p className="text-sm font-medium text-on-surface-variant">
                    No proposals yet — add availability to generate proposals.
                  </p>
                </div>
              )}

              {!isLoadingProposals && proposals && proposals.length > 0 && (
                <div className="space-y-3">
                  {proposals.map((proposal: ProposalResponse) => {
                    const start = new Date(proposal.start_time_utc)
                    const end = new Date(proposal.end_time_utc)
                    const dayLabel = start.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
                    const timeRange = `${start.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} – ${end.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`
                    return (
                      <div
                        key={proposal.id}
                        className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-outline-variant/20 space-y-2"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-sm font-bold text-on-surface">{dayLabel}</p>
                            <p className="text-xs font-medium text-on-surface-variant">{timeRange}</p>
                          </div>
                          <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0">
                            #{proposal.rank}
                          </span>
                        </div>
                        <p className="text-xs text-on-surface-variant">{proposal.reasoning}</p>
                        {isCoordinator && (
                          <button className="w-full py-2 rounded-lg bg-secondary-container text-on-secondary-container text-xs font-bold hover:bg-secondary-container/70 transition-colors">
                            Select
                          </button>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
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
    </div>
  )
}
