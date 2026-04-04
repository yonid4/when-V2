'use client'

import { useState, type FormEvent } from 'react'
import { UserPlus } from 'lucide-react'
import { useInvite } from '@/hooks/useInvitations'
import { useParticipants } from '@/hooks/useParticipants'
import type { Participant } from '@/types'

export function InviteInput({
  uid,
  coordinatorId,
  currentUserId,
}: {
  uid: string
  coordinatorId: string
  currentUserId: string
}) {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const { mutate: invite, isPending } = useInvite(uid)
  const { data: participants } = useParticipants(uid)

  const currentParticipant = participants?.find((p: Participant) => p.user_id === currentUserId)
  const isCoordinator = currentUserId === coordinatorId
  const canInvite = isCoordinator || currentParticipant?.can_invite

  if (!canInvite) return null

  function handleSubmit(e: FormEvent) {
    e.preventDefault()
    const trimmed = email.trim()
    if (!trimmed) {
      setError('Please enter an email address')
      return
    }
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    if (!emailRegex.test(trimmed)) {
      setError('Please enter a valid email address')
      return
    }
    setError(null)
    invite(trimmed, {
      onSuccess: () => setEmail(''),
      onError: (err: Error) => setError(err.message),
    })
  }

  return (
    <div className="flex flex-col gap-3">
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Invite by email…"
          className="flex-1 bg-surface-container-low rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:bg-surface-container-lowest transition-all"
        />
        <button
          type="submit"
          disabled={isPending}
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-gradient-to-br from-primary to-primary-container text-on-primary text-sm font-bold disabled:opacity-60 hover:-translate-y-0.5 transition-all duration-300"
        >
          <UserPlus className="w-4 h-4" />
          Invite
        </button>
      </form>
      {error && <p className="text-xs text-on-error-container bg-error-container px-3 py-1.5 rounded-lg">{error}</p>}
    </div>
  )
}
