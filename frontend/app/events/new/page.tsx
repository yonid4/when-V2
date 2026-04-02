'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import Link from 'next/link'
import {
  ArrowLeft,
  ArrowRight,
  Check,
  MapPin,
  Video,
  Users,
  PartyPopper,
  Cake,
  MoreHorizontal,
  Mail,
  X,
  CalendarDays,
  Clock,
  Timer,
  AlignLeft,
  Bell,
  CircleUser,
} from 'lucide-react'
import { useCreateEvent } from '@/hooks/useEvent'
import type { EventType } from '@/types'

// ─── Zod schemas ────────────────────────────────────────────────────────────

const step1Schema = z.object({
  name: z.string().min(1, 'Event name is required'),
  event_type: z.enum(['meeting', 'social', 'birthday', 'other']),
  description: z.string().optional(),
  location: z.string().optional(),
  video_call_link: z.string().url('Must be a valid URL').or(z.literal('')).optional(),
})

const step2Schema = z.object({
  earliest_date: z.string().min(1, 'Start date required'),
  latest_date: z.string().min(1, 'End date required'),
  duration_minutes: z.number().min(15),
  participant_emails: z.array(z.string().email()),
})

type Step1Values = z.infer<typeof step1Schema>
type Step2Values = z.infer<typeof step2Schema>

// ─── Combined wizard state ───────────────────────────────────────────────────

interface WizardData {
  step1: Step1Values
  step2: Step2Values
}

// ─── Step indicator ──────────────────────────────────────────────────────────

function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  const steps = ['Details', 'Availability', 'Confirm']
  return (
    <div className="flex items-center justify-between mb-12 relative px-4">
      <div className="absolute top-5 left-8 right-8 h-0.5 bg-surface-container-high -z-10" />
      {steps.map((label, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={label} className="flex flex-col items-center gap-2 bg-surface px-2">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300
                ${done ? 'bg-secondary-container text-on-secondary-container' : ''}
                ${active ? 'bg-gradient-to-br from-primary to-primary-container text-on-primary shadow-warm' : ''}
                ${!done && !active ? 'bg-surface-container-high text-on-surface-variant' : ''}
              `}
            >
              {done ? <Check className="w-4 h-4" /> : n}
            </div>
            <span
              className={`text-xs font-bold uppercase tracking-wider ${
                active ? 'text-primary' : done ? 'text-on-secondary-container' : 'text-on-surface-variant'
              }`}
            >
              {label}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ─── Event type cards ────────────────────────────────────────────────────────

const EVENT_TYPES: { value: EventType; label: string; icon: React.ReactNode }[] = [
  { value: 'meeting', label: 'Meeting', icon: <Users className="w-7 h-7 text-primary" /> },
  { value: 'social', label: 'Social', icon: <PartyPopper className="w-7 h-7 text-primary" /> },
  { value: 'birthday', label: 'Birthday', icon: <Cake className="w-7 h-7 text-primary" /> },
  { value: 'other', label: 'Other', icon: <MoreHorizontal className="w-7 h-7 text-primary" /> },
]

// ─── Duration options ────────────────────────────────────────────────────────

const DURATION_OPTIONS = [
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '1.5 hr', value: 90 },
  { label: '2 hr', value: 120 },
]

// ─── Top nav ─────────────────────────────────────────────────────────────────

function TopNav() {
  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/dashboard" className="text-2xl font-black text-primary tracking-tighter">When.</Link>
        <nav className="hidden md:flex items-center gap-8">
          <Link href="/dashboard" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Events</Link>
          <Link href="/calendar" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Calendar</Link>
          <Link href="/groups" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Groups</Link>
        </nav>
        <div className="flex items-center gap-3">
          <button className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
            <Bell className="w-5 h-5 text-on-surface-variant" />
          </button>
          <button className="w-9 h-9 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
            <CircleUser className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>
      </div>
    </header>
  )
}

// ─── Step 1 ──────────────────────────────────────────────────────────────────

function Step1({
  onNext,
  defaultValues,
}: {
  onNext: (data: Step1Values) => void
  defaultValues: Partial<Step1Values>
}) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Step1Values>({
    resolver: zodResolver(step1Schema),
    defaultValues: { event_type: 'social', ...defaultValues },
  })

  const selectedType = watch('event_type')

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-10">
      <div>
        <h2 className="text-3xl font-extrabold text-on-surface tracking-tight mb-2">Create a New Event</h2>
        <p className="text-on-surface-variant">Let's start with the basics. What are we celebrating?</p>
      </div>

      <div className="space-y-8">
        {/* Event name */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Event Name</label>
          <input
            {...register('name')}
            className="w-full bg-surface-container-low rounded-xl px-6 py-4 text-lg focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50"
            placeholder="E.g., Sunday Brunch at the Park"
          />
          {errors.name && <p className="text-sm text-error">{errors.name.message}</p>}
        </div>

        {/* Event type */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Event Type</label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {EVENT_TYPES.map(({ value, label, icon }) => (
              <button
                key={value}
                type="button"
                onClick={() => setValue('event_type', value)}
                className={`p-6 rounded-xl border-2 flex flex-col items-center gap-3 text-center transition-all duration-300
                  ${selectedType === value
                    ? 'border-primary bg-surface-container-lowest'
                    : 'border-transparent bg-surface-container-low hover:bg-surface-container-high'
                  }`}
              >
                {icon}
                <span className="font-bold text-on-surface text-sm">{label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Description */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Description (Optional)</label>
          <textarea
            {...register('description')}
            rows={3}
            className="w-full bg-surface-container-low rounded-xl px-6 py-4 text-base focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 resize-none"
            placeholder="Tell your guests a bit more about the plans..."
          />
        </div>

        {/* Location + Video call */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Location</label>
            <div className="relative">
              <MapPin className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-primary" />
              <input
                {...register('location')}
                className="w-full bg-surface-container-low rounded-xl pl-12 pr-6 py-4 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50"
                placeholder="Add a physical address"
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Video Call Link</label>
            <div className="relative">
              <Video className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-primary" />
              <input
                {...register('video_call_link')}
                type="url"
                className="w-full bg-surface-container-low rounded-xl pl-12 pr-6 py-4 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50"
                placeholder="Zoom, Meet, or Teams link"
              />
            </div>
            {errors.video_call_link && <p className="text-sm text-error">{errors.video_call_link.message}</p>}
          </div>
        </div>
      </div>

      <div className="flex flex-col-reverse md:flex-row items-center justify-between gap-6 pt-4">
        <Link
          href="/dashboard"
          className="flex items-center gap-2 text-on-surface-variant font-bold hover:text-primary transition-colors px-6 py-3"
        >
          <ArrowLeft className="w-5 h-5" />
          Back to Dashboard
        </Link>
        <button
          type="submit"
          className="w-full md:w-auto px-10 py-4 bg-gradient-to-br from-primary to-primary-container text-on-primary rounded-xl font-bold flex items-center justify-center gap-3 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-warm-md"
        >
          Next: Availability
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </form>
  )
}

// ─── Step 2 ──────────────────────────────────────────────────────────────────

function Step2({
  onNext,
  onBack,
  defaultValues,
}: {
  onNext: (data: Step2Values) => void
  onBack: () => void
  defaultValues: Partial<Step2Values>
}) {
  const {
    register,
    handleSubmit,
    watch,
    setValue,
    formState: { errors },
  } = useForm<Step2Values>({
    resolver: zodResolver(step2Schema),
    defaultValues: { duration_minutes: 60, participant_emails: [], ...defaultValues },
  })

  const [emailInput, setEmailInput] = useState('')
  const participantEmails = watch('participant_emails') ?? []
  const duration = watch('duration_minutes')

  function addEmail() {
    const email = emailInput.trim()
    if (!email || participantEmails.includes(email)) return
    setValue('participant_emails', [...participantEmails, email])
    setEmailInput('')
  }

  function removeEmail(email: string) {
    setValue('participant_emails', participantEmails.filter((e) => e !== email))
  }

  return (
    <form onSubmit={handleSubmit(onNext)} className="space-y-10">
      <div>
        <h2 className="text-3xl font-extrabold text-on-surface tracking-tight mb-2">Find the perfect window</h2>
        <p className="text-on-surface-variant">Define the timeframe and duration. We'll find the gaps for everyone.</p>
      </div>

      <div className="bg-surface-container-low p-8 rounded-xl space-y-6">
        {/* Date range */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Scheduling Window</label>
          <div className="flex items-center gap-3">
            <div className="flex-1 flex items-center bg-surface-container-lowest px-5 py-4 rounded-full border border-outline-variant/20 focus-within:ring-2 focus-within:ring-primary-fixed/50 transition-all gap-3">
              <CalendarDays className="w-4 h-4 text-primary shrink-0" />
              <input
                {...register('earliest_date')}
                type="date"
                className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
              />
            </div>
            <ArrowRight className="w-4 h-4 text-outline shrink-0" />
            <div className="flex-1 flex items-center bg-surface-container-lowest px-5 py-4 rounded-full border border-outline-variant/20 focus-within:ring-2 focus-within:ring-primary-fixed/50 transition-all">
              <input
                {...register('latest_date')}
                type="date"
                className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
              />
            </div>
          </div>
          {(errors.earliest_date || errors.latest_date) && (
            <p className="text-sm text-error">{errors.earliest_date?.message ?? errors.latest_date?.message}</p>
          )}
        </div>

        {/* Duration */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Duration</label>
          <div className="flex bg-surface-container-lowest p-1 rounded-full border border-outline-variant/20 overflow-x-auto">
            {DURATION_OPTIONS.map((opt) => (
              <button
                key={opt.value}
                type="button"
                onClick={() => setValue('duration_minutes', opt.value)}
                className={`px-4 py-2 rounded-full text-sm font-semibold whitespace-nowrap transition-all ${
                  duration === opt.value
                    ? 'bg-primary-container text-on-primary-container'
                    : 'text-on-surface-variant hover:bg-surface-container-high'
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Participants */}
      <div className="space-y-4">
        <div>
          <h3 className="text-lg font-bold text-on-surface">Participants</h3>
          <p className="text-sm text-on-surface-variant">Who's joining the discussion?</p>
        </div>

        <div className="bg-surface-container-low p-6 rounded-xl space-y-4">
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-outline" />
              <input
                type="email"
                value={emailInput}
                onChange={(e) => setEmailInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addEmail() } }}
                className="w-full pl-11 pr-4 py-4 rounded-full bg-surface-container-lowest focus:outline-none focus:ring-2 focus:ring-primary-fixed/50 text-on-surface placeholder:text-outline-variant"
                placeholder="Add by email..."
              />
            </div>
            <button
              type="button"
              onClick={addEmail}
              className="px-7 rounded-full bg-secondary text-on-secondary font-bold hover:opacity-90 transition-all"
            >
              Add
            </button>
          </div>

          {participantEmails.length > 0 && (
            <div className="space-y-2">
              {participantEmails.map((email) => (
                <div key={email} className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-2xl">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center">
                      <span className="text-sm font-bold text-on-surface-variant">{email[0].toUpperCase()}</span>
                    </div>
                    <span className="text-on-surface text-sm font-medium">{email}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="px-3 py-1 bg-secondary-container/50 text-on-secondary-container rounded-full text-xs font-bold uppercase tracking-wide">
                      Invited
                    </span>
                    <button
                      type="button"
                      onClick={() => removeEmail(email)}
                      className="p-1.5 text-outline-variant hover:text-error transition-colors"
                    >
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-2 px-8 py-4 rounded-full font-bold text-primary hover:bg-primary-fixed/30 transition-all"
        >
          <ArrowLeft className="w-5 h-5" />
          Back
        </button>
        <button
          type="submit"
          className="px-10 py-4 rounded-full bg-gradient-to-br from-primary to-primary-container text-on-primary font-bold flex items-center gap-2 transition-all duration-300 hover:-translate-y-0.5 hover:shadow-warm-md"
        >
          Next: Confirmation
          <ArrowRight className="w-5 h-5" />
        </button>
      </div>
    </form>
  )
}

// ─── Step 3 ──────────────────────────────────────────────────────────────────

function Step3({
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

  function formatDate(d: string) {
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

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
                {formatDate(step2.earliest_date)} – {formatDate(step2.latest_date)}
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

// ─── Page ────────────────────────────────────────────────────────────────────

export default function NewEventPage() {
  const router = useRouter()
  const { mutate: createEvent, isPending } = useCreateEvent()
  const [step, setStep] = useState<1 | 2 | 3>(1)
  const [wizardData, setWizardData] = useState<Partial<WizardData>>({})

  function handleStep1(data: Step1Values) {
    setWizardData((prev) => ({ ...prev, step1: data }))
    setStep(2)
  }

  function handleStep2(data: Step2Values) {
    setWizardData((prev) => ({ ...prev, step2: data }))
    setStep(3)
  }

  function handleSubmit() {
    const { step1, step2 } = wizardData as WizardData
    const earliest = new Date(`${step2.earliest_date}T00:00:00.000Z`)
    const latest = new Date(`${step2.latest_date}T23:59:59.000Z`)

    createEvent(
      {
        name: step1.name,
        description: step1.description || null,
        event_type: step1.event_type,
        location: step1.location || null,
        video_call_link: step1.video_call_link || null,
        earliest_datetime_utc: earliest.toISOString(),
        latest_datetime_utc: latest.toISOString(),
        duration_minutes: step2.duration_minutes,
      },
      {
        onSuccess: (event) => {
          router.push(`/events/${event.uid}`)
        },
      }
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      <TopNav />
      <main className="max-w-4xl mx-auto px-6 py-12">
        <StepIndicator current={step} />
        <div className="bg-surface-container-lowest rounded-xl p-8 md:p-12">
          {step === 1 && (
            <Step1
              onNext={handleStep1}
              defaultValues={wizardData.step1 ?? {}}
            />
          )}
          {step === 2 && (
            <Step2
              onNext={handleStep2}
              onBack={() => setStep(1)}
              defaultValues={wizardData.step2 ?? {}}
            />
          )}
          {step === 3 && wizardData.step1 && wizardData.step2 && (
            <Step3
              data={wizardData as WizardData}
              onBack={() => setStep(2)}
              onSubmit={handleSubmit}
              isLoading={isPending}
            />
          )}
        </div>
      </main>
    </div>
  )
}
