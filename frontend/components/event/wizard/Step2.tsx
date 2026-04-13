'use client'

import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, ArrowRight, CalendarDays, Clock, Mail, X } from 'lucide-react'
import type { Step2Values } from '@/types'

const step2Schema = z.object({
  earliest_date: z.string().min(1, 'Start date required'),
  latest_date: z.string().min(1, 'End date required'),
  start_time: z.string().min(1, 'Start time required'),
  end_time: z.string().min(1, 'End time required'),
  duration_minutes: z.number().min(15),
  participant_emails: z.array(z.string().email()),
})

export function validateStep2Times(
  data: Pick<Step2Values, 'earliest_date' | 'latest_date' | 'start_time' | 'end_time'>
): { field: 'latest_date' | 'end_time'; message: string } | null {
  if (data.latest_date < data.earliest_date) {
    return { field: 'latest_date', message: 'End date must be on or after start date' }
  }
  if (data.latest_date === data.earliest_date && data.end_time <= data.start_time) {
    return { field: 'end_time', message: 'End time must be after start time on the same day' }
  }
  return null
}

const DURATION_OPTIONS = [
  { label: '30 min', value: 30 },
  { label: '1 hr', value: 60 },
  { label: '1.5 hr', value: 90 },
  { label: '2 hr', value: 120 },
]

export function Step2({
  onNext,
  onBack,
  defaultValues,
}: {
  onNext: (data: Step2Values) => void
  onBack: () => void
  defaultValues: Partial<Step2Values>
}) {
  const today = new Date().toISOString().split('T')[0]
  const sevenDaysFromNow = new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0]

  const initialDefaults: Partial<Step2Values> = {
    earliest_date: today,
    latest_date: sevenDaysFromNow,
    start_time: '09:00',
    end_time: '17:00',
    duration_minutes: 60,
    participant_emails: [],
  }

  const {
    register,
    handleSubmit,
    watch,
    setValue,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm<Step2Values>({
    resolver: zodResolver(step2Schema),
    defaultValues: { ...initialDefaults, ...defaultValues },
  })

  const [emailInput, setEmailInput] = useState('')
  const participantEmails = watch('participant_emails') ?? []
  const duration = watch('duration_minutes')
  const earliestDate = watch('earliest_date')

  function addEmail() {
    const email = emailInput.trim()
    if (!email || participantEmails.includes(email)) return
    setValue('participant_emails', [...participantEmails, email])
    setEmailInput('')
  }

  function removeEmail(email: string) {
    setValue('participant_emails', participantEmails.filter((e) => e !== email))
  }

  function handleEarliestDateChange(e: React.ChangeEvent<HTMLInputElement>) {
    const newStart = e.target.value
    setValue('earliest_date', newStart)
    const currentEnd = watch('latest_date')
    if (currentEnd && currentEnd < newStart) {
      setValue('latest_date', '')
    }
  }

  function onSubmit(data: Step2Values) {
    const validationError = validateStep2Times(data)
    if (validationError) {
      setError(validationError.field, { message: validationError.message })
      return
    }
    clearErrors()
    onNext(data)
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-10">
      <div>
        <h2 className="text-3xl font-extrabold text-on-surface tracking-tight mb-2">Find the perfect window</h2>
        <p className="text-on-surface-variant">Define the timeframe and duration. We&apos;ll find the gaps for everyone.</p>
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
                min={today}
                onChange={handleEarliestDateChange}
                className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
              />
            </div>
            <ArrowRight className="w-4 h-4 text-outline shrink-0" />
            <div className="flex-1 flex items-center bg-surface-container-lowest px-5 py-4 rounded-full border border-outline-variant/20 focus-within:ring-2 focus-within:ring-primary-fixed/50 transition-all">
              <input
                {...register('latest_date')}
                type="date"
                min={earliestDate || today}
                className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
              />
            </div>
          </div>
          {(errors.earliest_date || errors.latest_date) && (
            <p className="text-sm text-error">{errors.earliest_date?.message ?? errors.latest_date?.message}</p>
          )}
        </div>

        {/* Time of day range */}
        <div className="space-y-2">
          <label className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">Time of Day</label>
          <div className="flex items-center gap-3">
            <div className="flex-1 space-y-1">
              <label className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">Start Time</label>
              <div className="flex items-center bg-surface-container-lowest px-5 py-4 rounded-full border border-outline-variant/20 focus-within:ring-2 focus-within:ring-primary-fixed/50 transition-all gap-3">
                <Clock className="w-4 h-4 text-primary shrink-0" />
                <input
                  {...register('start_time')}
                  type="time"
                  className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
                />
              </div>
              {errors.start_time && <p className="text-sm text-error">{errors.start_time.message}</p>}
            </div>
            <ArrowRight className="w-4 h-4 text-outline shrink-0 mt-5" />
            <div className="flex-1 space-y-1">
              <label className="text-[10px] font-semibold text-on-surface-variant uppercase tracking-wider">End Time</label>
              <div className="flex items-center bg-surface-container-lowest px-5 py-4 rounded-full border border-outline-variant/20 focus-within:ring-2 focus-within:ring-primary-fixed/50 transition-all gap-3">
                <Clock className="w-4 h-4 text-primary shrink-0" />
                <input
                  {...register('end_time')}
                  type="time"
                  className="bg-transparent focus:outline-none w-full text-on-surface font-medium"
                />
              </div>
              {errors.end_time && <p className="text-sm text-error">{errors.end_time.message}</p>}
            </div>
          </div>
          <p className="text-xs text-on-surface-variant/70 pt-0.5">Times shown in your local timezone.</p>
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
          <p className="text-sm text-on-surface-variant">Who&apos;s joining the discussion?</p>
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
