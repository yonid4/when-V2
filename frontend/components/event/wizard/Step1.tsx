'use client'

import Link from 'next/link'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { ArrowLeft, ArrowRight, MapPin, Video, Users, PartyPopper, Cake, MoreHorizontal } from 'lucide-react'
import type { EventType, Step1Values } from '@/types'

const step1Schema = z.object({
  name: z.string().min(1, 'Event name is required'),
  event_type: z.enum(['meeting', 'social', 'birthday', 'other']),
  description: z.string().optional(),
  location: z.string().optional(),
  video_call_link: z.string().url('Must be a valid URL').or(z.literal('')).optional(),
})

const EVENT_TYPES: { value: EventType; label: string; icon: React.ReactNode }[] = [
  { value: 'meeting', label: 'Meeting', icon: <Users className="w-7 h-7 text-primary" /> },
  { value: 'social', label: 'Social', icon: <PartyPopper className="w-7 h-7 text-primary" /> },
  { value: 'birthday', label: 'Birthday', icon: <Cake className="w-7 h-7 text-primary" /> },
  { value: 'other', label: 'Other', icon: <MoreHorizontal className="w-7 h-7 text-primary" /> },
]

export function Step1({
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
