'use client'

import {
  ArrowLeft,
  MapPin,
  Video,
  Users,
  PartyPopper,
  Cake,
  MoreHorizontal,
  CalendarDays,
  Timer,
  AlignLeft,
} from 'lucide-react'
import { formatShortDate } from '@/lib/dates'
import type { EventType, WizardData } from '@/types'

const DURATION_OPTIONS = [
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '1.5 hr', value: 90 },
  { label: '2 hr', value: 120 },
]

export function Step3({
  data,
  onBack,
  onSubmit,
  isLoading,
}: {
  data: WizardData
  onBack: () => void
  onSubmit: () => void
  isLoading: boolean
}) {
  const { step1, step2 } = data

  const eventTypeIcon: Record<EventType, React.ReactNode> = {
    meeting: <Users className="w-4 h-4" />,
    social: <PartyPopper className="w-4 h-4" />,
    birthday: <Cake className="w-4 h-4" />,
    other: <MoreHorizontal className="w-4 h-4" />,
  }

  const durationLabel = DURATION_OPTIONS.find((o) => o.value === step2.duration_minutes)?.label
    ?? `${step2.duration_minutes} min`

  return (
    <div className="space-y-8">
      <div className="text-center">
        <h2 className="text-4xl font-extrabold text-on-surface tracking-tight mb-2">Almost there.</h2>
        <p className="text-on-surface-variant font-medium">Review your invitation details before sending.</p>
      </div>

      {/* Receipt card */}
      <div className="bg-surface-container-lowest rounded-xl p-8 relative overflow-hidden">
        <div className="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-primary to-primary-container" />

        <div className="mb-6">
          <span className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-secondary-container text-on-secondary-container text-sm font-semibold capitalize">
            {eventTypeIcon[step1.event_type]}
            {step1.event_type}
          </span>
        </div>

        <h3 className="text-3xl font-black text-on-surface mb-8 tracking-tighter">{step1.name}</h3>

        <div className="space-y-5">
          {step1.description && (
            <div className="flex gap-4">
              <AlignLeft className="w-5 h-5 text-primary mt-0.5 shrink-0" />
              <p className="text-on-surface-variant text-sm leading-relaxed">{step1.description}</p>
            </div>
          )}
          {step1.location && (
            <div className="flex gap-4 items-center">
              <MapPin className="w-5 h-5 text-primary shrink-0" />
              <span className="text-on-surface font-medium">{step1.location}</span>
            </div>
          )}
          {step1.video_call_link && (
            <div className="flex gap-4 items-center">
              <Video className="w-5 h-5 text-primary shrink-0" />
              <span className="text-on-surface text-sm break-all">{step1.video_call_link}</span>
            </div>
          )}

          {/* Time block */}
          <div className="bg-surface-container-low rounded-2xl p-5 space-y-4">
            <div className="flex justify-between items-center border-b border-outline-variant/20 pb-3">
              <div className="flex items-center gap-3">
                <CalendarDays className="w-5 h-5 text-primary" />
                <span className="text-sm font-bold text-on-surface">Window</span>
              </div>
              <span className="text-sm text-on-surface-variant font-medium">
                {formatShortDate(step2.earliest_date)} – {formatShortDate(step2.latest_date)}
              </span>
            </div>
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-3">
                <Timer className="w-5 h-5 text-primary" />
                <span className="text-sm font-bold text-on-surface">Duration</span>
              </div>
              <span className="text-sm text-on-surface-variant font-medium">{durationLabel}</span>
            </div>
          </div>

          {/* Participants */}
          {step2.participant_emails.length > 0 && (
            <div className="pt-2">
              <h4 className="text-sm font-bold text-on-surface mb-3">
                Participants ({step2.participant_emails.length})
              </h4>
              <p className="text-xs text-on-surface-variant">{step2.participant_emails.join(', ')}</p>
            </div>
          )}
        </div>
      </div>

      {/* Actions */}
      <div className="flex flex-col items-center gap-4">
        <button
          onClick={onSubmit}
          disabled={isLoading}
          className="w-full py-5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold text-lg transition-all duration-500 hover:-translate-y-1 hover:shadow-warm-md disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Creating…' : 'Create Event'}
        </button>
        <button
          onClick={onBack}
          className="flex items-center gap-2 text-primary font-bold hover:opacity-80 transition-opacity"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to edit
        </button>
      </div>
    </div>
  )
}
