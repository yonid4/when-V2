'use client'

import { useState, useEffect } from 'react'
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
import { usePreferredSlots } from '@/hooks/usePreferredSlots'
import { supabase } from '@/lib/supabase'
import { ParticipantList } from '@/components/event/ParticipantList'
import { InviteInput } from '@/components/event/InviteInput'
import { RsvpSelector } from '@/components/event/RsvpSelector'
import { Navbar } from '@/components/layout/Navbar'
import { useAuthStore } from '@/stores/authStore'
import type { BusySlot, EventWithParticipants, EventType } from '@/types'
import { getSlotsForCell } from '@/lib/gridUtils'
import type { SlotLike } from '@/lib/gridUtils'
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
// Internal logic is unchanged. Only the wrapper styling matches the design HTML.

function busyClass(count: number): string {
  if (count >= 7) return 'bg-error/90'
  if (count >= 5) return 'bg-error/65'
  if (count >= 3) return 'bg-error/40'
  return 'bg-error/20'
}

function preferredClass(count: number): string {
  if (count >= 7) return 'bg-secondary/90'
  if (count >= 5) return 'bg-secondary/65'
  if (count >= 3) return 'bg-secondary/40'
  return 'bg-secondary/20'
}

function formatTimeRange(hour: number, half: number): string {
  const startH = String(hour).padStart(2, '0')
  const startM = half === 0 ? '00' : '30'
  const endHour = half === 0 ? hour : hour + 1
  const endH = String(endHour).padStart(2, '0')
  const endM = half === 0 ? '30' : '00'
  return `${startH}:${startM} – ${endH}:${endM}`
}

function AvailabilityGrid({
  busySlots,
  preferredSlots,
  startDate,
  earliestTime,
  latestTime,
}: {
  busySlots: SlotLike[]
  preferredSlots: SlotLike[]
  startDate: string
  earliestTime: string
  latestTime: string
}) {
  const earliestDate = new Date(earliestTime)
  const latestDate = new Date(latestTime)
  // Use local hours so the grid displays times in the user's timezone
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

  // Month indicator — "Apr 2026" or "Mar – Apr 2026" if week spans two months
  const firstDay = days[0]
  const lastDay = days[6]
  const monthLabel = firstDay.month === lastDay.month
    ? `${firstDay.month} ${firstDay.year}`
    : `${firstDay.month} – ${lastDay.month} ${lastDay.year}`

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-surface-container-lowest rounded-xl p-6 shadow-[0_20px_40px_-15px_rgba(155,68,40,0.05)]">
      {/* Week nav + month indicator */}
      <div className="flex items-center justify-between mb-3 shrink-0">
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

      {/* Day headers */}
      <div className="grid grid-cols-[80px_1fr] border-b border-outline-variant/25 shrink-0">
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

      {/* Grid body — scrollable if > 8 hours, otherwise fills height */}
      <div className={`flex flex-col flex-1 min-h-0 ${isScrollable ? 'overflow-y-auto' : 'overflow-hidden'}`}>
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
                // Build a local-midnight Date for this column's day
                const colDate = new Date(baseDate)
                colDate.setDate(colDate.getDate() + di)

                return (
                  <div key={di} className={`flex flex-col ${isScrollable ? '' : 'flex-1'} ${di < 6 ? 'border-r border-outline-variant/25' : ''}`}>
                    {Array.from({ length: totalHours }, (_, hi) => {
                      const hour = startHour + hi
                      return [0, 1].map((half) => {
                        // Build cell boundaries in local time so they match local slot times
                        const cellStartUtc = new Date(
                          colDate.getFullYear(),
                          colDate.getMonth(),
                          colDate.getDate(),
                          hour,
                          half === 0 ? 0 : 30,
                        )
                        const cellEndUtc = new Date(
                          colDate.getFullYear(),
                          colDate.getMonth(),
                          colDate.getDate(),
                          half === 0 ? hour : hour + 1,
                          half === 0 ? 30 : 0,
                        )

                        const busyCount = getSlotsForCell(cellStartUtc, cellEndUtc, busySlots).length
                        const preferredCount = getSlotsForCell(cellStartUtc, cellEndUtc, preferredSlots).length
                        const timeLabel = formatTimeRange(hour, half)
                        const halfClass = isScrollable ? 'h-8' : 'flex-1'

                        if (busyCount > 0 && preferredCount > 0) {
                          // Conflict — split cell vertically
                          return (
                            <div
                              key={`${hi}-${half}`}
                              className={`relative flex flex-row border-b border-outline-variant/20 cursor-default ${halfClass}`}
                            >
                              <div className={`w-1/2 h-full ${busyClass(busyCount)}`} />
                              <div className={`w-1/2 h-full ${preferredClass(preferredCount)}`} />
                              <span className="absolute inset-0 flex items-center justify-center text-[9px] font-bold uppercase text-error pointer-events-none">
                                CONFLICT
                              </span>
                            </div>
                          )
                        }

                        if (busyCount > 0) {
                          return (
                            <div
                              key={`${hi}-${half}`}
                              className={`relative flex items-center justify-center border-b border-outline-variant/20 cursor-default ${busyClass(busyCount)} ${halfClass}`}
                            >
                              <span className="text-[9px] font-semibold text-white pointer-events-none">
                                {timeLabel}
                              </span>
                            </div>
                          )
                        }

                        if (preferredCount > 0) {
                          return (
                            <div
                              key={`${hi}-${half}`}
                              className={`relative flex items-center justify-center border-b border-outline-variant/20 cursor-default ${preferredClass(preferredCount)} ${halfClass}`}
                            >
                              <span className="text-[9px] font-semibold text-white pointer-events-none">
                                {timeLabel}
                              </span>
                            </div>
                          )
                        }

                        // Empty cell
                        return (
                          <div
                            key={`${hi}-${half}`}
                            className={`border-b border-outline-variant/20 hover:bg-surface-container-high cursor-pointer transition-colors ${halfClass}`}
                          />
                        )
                      })
                    })}
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

  // Local event state — updated optimistically after edits so the UI reflects
  // changes without a full page reload
  const [event, setEvent] = useState(initialEvent)
  // Bumping this key force-remounts ParticipantList to re-fetch when allow_guest_invites changes
  const [participantsKey, setParticipantsKey] = useState(0)

  const isCoordinator = !!user?.id && user.id === event.coordinator_id

  const [showEdit, setShowEdit] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const [showInvite, setShowInvite] = useState(false)
  const [copyLabel, setCopyLabel] = useState('Copy Link')

  function handleSave(result: EditSaveResult) {
    if (result.infoChanged || result.timeRangeChanged) {
      setEvent((prev) => ({ ...prev, ...result.updated }))
    }
    if (result.guestInvitesChanged) {
      setParticipantsKey((k) => k + 1)
    }
    if (result.durationChanged || result.timeRangeChanged) {
      // TODO: trigger proposed times algorithm once it exists
    }
  }

  const queryClient = useQueryClient()
  const { data: busySlots = [] } = useEventBusySlots(event.uid)
  const { data: preferredSlots = [] } = usePreferredSlots(event.uid)
  const { mutate: syncCalendar, isPending: isSyncing } = useSyncMyCalendar()

  // Real-time subscription: invalidate preferred slots on INSERT or DELETE
  useEffect(() => {
    if (!event.id) return
    const channel = supabase
      .channel(`preferred-slots-${event.id}`)
      .on(
        'postgres_changes',
        { event: 'INSERT', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${event.id}` },
        () => queryClient.invalidateQueries({ queryKey: ['preferred-slots', event.uid] })
      )
      .on(
        'postgres_changes',
        { event: 'DELETE', schema: 'public', table: 'preferred_slots', filter: `event_id=eq.${event.id}` },
        () => queryClient.invalidateQueries({ queryKey: ['preferred-slots', event.uid] })
      )
      .subscribe()
    return () => { supabase.removeChannel(channel) }
  }, [event.id, event.uid, queryClient])
  const { mutate: syncAll, isPending: isSyncingAll } = useSyncCalendar(event.uid)

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

        {/* ── Left: Availability Grid ──
              design: flex-1 h-full overflow-y-auto p-6 lg:p-8 bg-surface */}
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

            <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
              <AvailabilityGrid
                busySlots={busySlots}
                preferredSlots={preferredSlots}
                startDate={event.earliest_datetime_utc}
                earliestTime={event.earliest_datetime_utc}
                latestTime={event.latest_datetime_utc}
              />
            </div>
          </div>
        </section>

        {/* ── Right: Event Info + Actions ──
              design: w-full md:w-[400px] lg:w-[450px] h-full overflow-y-auto
                      hide-scrollbar bg-surface-container-low p-6 flex flex-col
                      gap-8 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.03)] z-10 */}
        <section className="w-full md:w-[456px] shrink-0 lg:w-[504px] xl:w-[552px] h-full overflow-y-auto hide-scrollbar bg-surface-container-low p-6 flex flex-col gap-8 shadow-[-20px_0_40px_-15px_rgba(0,0,0,0.03)] z-10">

          {/* ── Section 1: Event Header card ──
                design: bg-surface-container-lowest p-6 rounded-lg relative shadow-sm */}
          <div className="bg-surface-container-lowest p-6 rounded-lg relative shadow-sm">

            {/* Edit pencil — coordinator only, absolute top-right */}
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

            {/* View Proposed Times — full-width gradient button */}
            <button
              onClick={() => { /* wired in Sprint 5 */ }}
              className="w-full py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold shadow-[0_15px_30px_-10px_rgba(155,68,40,0.3)] flex items-center justify-center gap-2 transform hover:-translate-y-0.5 transition-all duration-300"
            >
              {/* auto_awesome equivalent */}
              <svg className="w-5 h-5" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                <path d="M12 2l2.09 6.26L20 10l-5.91 1.74L12 18l-2.09-6.26L4 10l5.91-1.74z" />
              </svg>
              View Proposed Times
            </button>

            {/* 2×2 grid of secondary action buttons — only renders visible buttons */}
            <div className="grid grid-cols-2 gap-3">

              {/* Refresh — always visible */}
              <button
                onClick={() => syncCalendar()}
                disabled={isSyncing}
                className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors disabled:opacity-60"
              >
                <RefreshCw className={`w-[18px] h-[18px] flex-shrink-0 ${isSyncing ? 'animate-spin' : ''}`} />
                {isSyncing ? 'Syncing…' : 'Refresh'}
              </button>

              {/* Invite — coordinator or can_invite; empty cell otherwise */}
              {canInvite ? (
                <button
                  onClick={() => setShowInvite((v) => !v)}
                  className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors"
                >
                  <UserPlus className="w-[18px] h-[18px] flex-shrink-0" />
                  Invite
                </button>
              ) : null}

              {/* Copy Link — always visible */}
              <button
                onClick={handleCopyLink}
                className="p-3 bg-surface-container-lowest border-2 border-outline-variant/30 text-on-surface-variant rounded-xl text-xs font-bold flex items-center gap-2 hover:bg-white transition-colors"
              >
                <Link2 className="w-[18px] h-[18px] flex-shrink-0" />
                {copyLabel}
              </button>

              {/* Sync All — coordinator only */}
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

            {/* InviteInput — shown inline when Invite is toggled */}
            {showInvite && (
              <InviteInput
                uid={event.uid}
                coordinatorId={event.coordinator_id}
                currentUserId={currentUserId}
              />
            )}
          </div>

          {/* RSVP selector — component handles its own coordinator guard */}
          <RsvpSelector uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />

          {/* ── Section 3: Top Proposals ──
                Sprint 5 placeholder — real cards wired later */}
          <div className="space-y-4">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em] px-1">
              Top Proposals
            </label>
            <div className="bg-surface-container-lowest p-4 rounded-xl flex items-center gap-4 shadow-sm">
              <div className="h-10 w-10 bg-surface-container-low rounded-lg flex items-center justify-center text-primary flex-shrink-0">
                <Calendar className="w-5 h-5" />
              </div>
              <p className="text-sm font-medium text-on-surface-variant">
                No proposals yet — proposals will appear here once the algorithm runs.
              </p>
            </div>
          </div>

          {/* ── Section 4: Participants ── */}
          <div className="space-y-4 pb-12">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em] px-1">
              Participants ({event.participants.length})
            </label>
            {/* ParticipantList owns all participant fetching, remove, and
                permission-toggle logic — only styling wraps it here */}
            <div className="space-y-1">
              <ParticipantList
                key={participantsKey}
                uid={event.uid}
                coordinatorId={event.coordinator_id}
                currentUserId={currentUserId}
              />
            </div>
          </div>

          {/* Delete event — coordinator only, at bottom of panel */}
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
