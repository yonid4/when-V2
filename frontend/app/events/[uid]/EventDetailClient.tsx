'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import {
  RefreshCw,
  MapPin,
  Trash2,
  Pencil,
  X,
  Check,
} from 'lucide-react'
import { useUpdateEvent, useDeleteEvent } from '@/hooks/useEvent'
import { useEventBusySlots, useSyncCalendar } from '@/hooks/useBusySlots'
import { ParticipantList } from '@/components/event/ParticipantList'
import { InviteInput } from '@/components/event/InviteInput'
import { RsvpSelector } from '@/components/event/RsvpSelector'
import { Navbar } from '@/components/layout/Navbar'
import type { BusySlot, EventWithParticipants, EventType } from '@/types'

// ─── Edit modal ──────────────────────────────────────────────────────────────

const editSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  description: z.string().optional(),
  location: z.string().optional(),
  video_call_link: z.string().url('Must be a valid URL').or(z.literal('')).optional(),
})
type EditValues = z.infer<typeof editSchema>

function EditModal({
  event,
  onClose,
}: {
  event: EventWithParticipants
  onClose: () => void
}) {
  const { mutate: updateEvent, isPending } = useUpdateEvent(event.uid)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<EditValues>({
    resolver: zodResolver(editSchema),
    defaultValues: {
      name: event.name,
      description: event.description ?? '',
      location: event.location ?? '',
      video_call_link: event.video_call_link ?? '',
    },
  })

  function onSubmit(data: EditValues) {
    updateEvent(
      {
        name: data.name,
        description: data.description || null,
        location: data.location || null,
        video_call_link: data.video_call_link || null,
      },
      { onSuccess: onClose }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-lg shadow-warm-md">
        <div className="flex items-center justify-between p-6 border-b border-outline-variant/20">
          <h2 className="text-xl font-bold text-on-surface">Edit Event</h2>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-surface-container transition-colors">
            <X className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="p-6 space-y-5">
          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Event Name</label>
            <input
              {...register('name')}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
            />
            {errors.name && <p className="text-sm text-error">{errors.name.message}</p>}
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Description</label>
            <textarea
              {...register('description')}
              rows={3}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all resize-none"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Location</label>
            <input
              {...register('location')}
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-wider">Video Call Link</label>
            <input
              {...register('video_call_link')}
              type="url"
              className="w-full bg-surface-container-low rounded-xl px-5 py-3.5 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all"
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

// ─── Availability grid (static shell) ────────────────────────────────────────

function AvailabilityGrid({ busySlots }: { busySlots: BusySlot[] }) {
  const hours = ['09:00 AM', '10:00 AM', '11:00 AM', '12:00 PM', '01:00 PM', '02:00 PM', '03:00 PM', '04:00 PM', '05:00 PM']
  const days = ['MON', 'TUE', 'WED', 'THU', 'FRI']

  return (
    <div className="bg-surface-container-lowest rounded-xl p-6 overflow-hidden">
      {/* Day headers */}
      <div className="grid grid-cols-[64px_1fr] mb-2">
        <div />
        <div className="grid grid-cols-5">
          {days.map((d, i) => (
            <div key={d} className={`text-center text-xs font-bold text-on-surface-variant py-3 ${i < 4 ? 'border-r border-outline-variant/10' : ''}`}>
              {d}
            </div>
          ))}
        </div>
      </div>

      {/* Body */}
      <div className="h-[480px] overflow-y-auto">
        <div className="grid grid-cols-[64px_1fr]">
          {/* Time labels */}
          <div className="flex flex-col">
            {hours.map((h) => (
              <div key={h} className="h-16 flex items-start justify-end pr-3 pt-1">
                <span className="text-[10px] text-on-surface-variant/60 font-medium whitespace-nowrap">{h}</span>
              </div>
            ))}
          </div>

          {/* Grid cells */}
          <div className="grid grid-cols-5">
            {days.map((d, di) => (
              <div key={d} className={`flex flex-col ${di < 4 ? 'border-r border-outline-variant/10' : ''}`}>
                {hours.map((h) => (
                  <div
                    key={h}
                    className="h-16 border-b border-outline-variant/5 hover:bg-surface-container-high cursor-pointer transition-colors"
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ─── Right panel ─────────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: 'bg-secondary-container text-on-secondary-container',
    planning: 'bg-surface-container-high text-on-surface-variant',
    cancelled: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`text-xs font-bold uppercase px-3 py-1 rounded-full ${styles[status] ?? styles.planning}`}>
      {status}
    </span>
  )
}

function typeLabel(t: EventType) {
  return t.charAt(0).toUpperCase() + t.slice(1)
}

function formatDateWindow(earliest: string, latest: string) {
  const fmt = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
  return `${fmt(earliest)} – ${fmt(latest)}`
}

// ─── Main export ─────────────────────────────────────────────────────────────

export default function EventDetailClient({
  event,
  isCoordinator,
  currentUserId,
}: {
  event: EventWithParticipants
  isCoordinator: boolean
  currentUserId: string
}) {
  const [showEdit, setShowEdit] = useState(false)
  const [showDelete, setShowDelete] = useState(false)
  const { data: busySlots = [] } = useEventBusySlots(event.uid)
  const { mutate: syncCalendar, isPending: isSyncing } = useSyncCalendar(event.uid)

  return (
    <>
      <Navbar />

      <main className="max-w-7xl mx-auto px-6 py-8 flex flex-col md:flex-row gap-8">
        {/* Left — availability grid */}
        <section className="w-full md:w-[65%] flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-bold text-on-surface-variant tracking-tight">Availability Grid</h2>
            <div className="flex flex-wrap gap-4 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-error inline-block" /> Busy</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-secondary inline-block" /> Preferred</span>
              <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 rounded-full bg-primary-container/40 inline-block" /> Proposed</span>
            </div>
          </div>
          <AvailabilityGrid busySlots={busySlots} />
        </section>

        {/* Right — info panel */}
        <aside className="w-full md:w-[35%] flex flex-col gap-6">
          {/* Event card */}
          <div className="bg-surface-container-low rounded-xl p-6 flex flex-col gap-4">
            <div className="flex flex-wrap gap-2">
              <span className="px-3 py-1 bg-primary-container/20 text-on-primary-container text-xs font-bold rounded-full capitalize">
                {typeLabel(event.event_type)}
              </span>
              <StatusBadge status={event.status} />
            </div>

            <div>
              <h1 className="text-3xl font-extrabold text-on-surface leading-tight tracking-tight">{event.name}</h1>
              <p className="text-on-surface-variant/70 mt-1 text-sm font-medium">
                {formatDateWindow(event.earliest_datetime_utc, event.latest_datetime_utc)}
              </p>
            </div>

            {event.location && (
              <div className="flex items-center gap-2 text-primary font-medium text-sm">
                <MapPin className="w-4 h-4" />
                <span>{event.location}</span>
              </div>
            )}

            {/* Coordinator actions */}
            {isCoordinator && (
              <div className="flex gap-2 pt-1">
                <button
                  onClick={() => setShowEdit(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-surface-container text-on-surface-variant text-xs font-bold hover:bg-surface-container-high transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  Edit
                </button>
                <button
                  onClick={() => setShowDelete(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-error-container text-on-error-container text-xs font-bold hover:opacity-80 transition-opacity"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                  Delete
                </button>
              </div>
            )}
          </div>

          {/* Actions */}
          <div className="grid grid-cols-2 gap-3">
            <button className="col-span-2 flex items-center justify-center gap-2 py-3.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold transition-all duration-300 hover:-translate-y-0.5 hover:shadow-warm-md">
              View proposed times
            </button>
            <button
              onClick={() => syncCalendar()}
              disabled={isSyncing}
              className="flex flex-col items-center gap-1 bg-surface-container-lowest text-on-surface-variant p-3 rounded-xl hover:bg-surface-container-high transition-colors text-xs font-bold disabled:opacity-60"
            >
              <RefreshCw className={`w-5 h-5 text-primary mb-1 ${isSyncing ? 'animate-spin' : ''}`} />
              {isSyncing ? 'Syncing…' : 'Sync calendar'}
            </button>
            <InviteInput uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />
          </div>

          {/* RSVP selector for non-coordinators */}
          <RsvpSelector uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />

          {/* Participants */}
          <ParticipantList uid={event.uid} coordinatorId={event.coordinator_id} currentUserId={currentUserId} />
        </aside>
      </main>

      {/* Modals */}
      {showEdit && <EditModal event={event} onClose={() => setShowEdit(false)} />}
      {showDelete && <DeleteModal event={event} onClose={() => setShowDelete(false)} />}
    </>
  )
}
