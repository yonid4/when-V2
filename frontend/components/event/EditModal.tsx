'use client'

import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { X, Check } from 'lucide-react'
import { useUpdateEvent } from '@/hooks/useEvent'
import type { EventWithParticipants } from '@/types'
import {
  editSchema,
  toDatetimeLocal,
  computeEditDiff,
} from '@/app/events/[uid]/editEventUtils'
import type { EditValues, EditSaveResult } from '@/app/events/[uid]/editEventUtils'

export function EditModal({
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
