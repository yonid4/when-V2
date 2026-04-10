'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useCreateEvent } from '@/hooks/useEvent'
import { useInviteParticipant } from '@/hooks/useInvitations'
import type { Step1Values, Step2Values, WizardData } from '@/types'
import { StepIndicator } from '@/components/event/wizard/StepIndicator'
import { Step1 } from '@/components/event/wizard/Step1'
import { Step2 } from '@/components/event/wizard/Step2'
import { Step3 } from '@/components/event/wizard/Step3'
import { Navbar } from '@/components/layout/Navbar'

// ─── Page ────────────────────────────────────────────────────────────────────

export default function NewEventPage() {
  const router = useRouter()
  const { mutate: createEvent, isPending } = useCreateEvent()
  const { mutateAsync: inviteParticipant } = useInviteParticipant()
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

  async function handleSubmit() {
    const { step1, step2 } = wizardData as WizardData
    const earliest = new Date(`${step2.earliest_date}T${step2.start_time}:00`)
    const latest = new Date(`${step2.latest_date}T${step2.end_time}:00`)

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
        onSuccess: async (event) => {
          for (const email of step2.participant_emails) {
            await inviteParticipant({ uid: event.uid, email })
          }
          router.push(`/events/${event.uid}`)
        },
      }
    )
  }

  return (
    <div className="min-h-screen bg-surface">
      <Navbar />
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
