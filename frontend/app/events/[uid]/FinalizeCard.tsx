'use client'

import { useState } from 'react'
import { X, CalendarCheck, Plus } from 'lucide-react'
import { useFinalize } from '@/hooks/useFinalize'
import type { Event, Participant, ProposalResponse } from '@/types'

interface FinalizeCardProps {
  event: Event
  proposals: ProposalResponse[]
  acceptedParticipants: Participant[]
  onClose: () => void
  onSuccess: () => void
}

export function FinalizeCard({
  event,
  proposals,
  acceptedParticipants,
  onClose,
  onSuccess,
}: FinalizeCardProps) {
  const [name, setName] = useState(event.name)
  const [selectedProposalId, setSelectedProposalId] = useState<string>('')
  const [excludedUserIds, setExcludedUserIds] = useState<Set<string>>(new Set())
  const [extraEmailInput, setExtraEmailInput] = useState('')
  const [extraEmails, setExtraEmails] = useState<string[]>([])
  const [note, setNote] = useState(event.description ?? '')
  const [location, setLocation] = useState(event.location ?? '')
  const [videoCallLink, setVideoCallLink] = useState(event.video_call_link ?? '')
  const [apiError, setApiError] = useState<string | null>(null)

  const { mutate: finalize, isPending } = useFinalize(event.uid)

  function toggleParticipant(userId: string) {
    setExcludedUserIds((prev) => {
      const next = new Set(prev)
      if (next.has(userId)) {
        next.delete(userId)
      } else {
        next.add(userId)
      }
      return next
    })
  }

  function addExtraEmail() {
    const trimmed = extraEmailInput.trim()
    if (!trimmed || extraEmails.includes(trimmed)) return
    setExtraEmails((prev) => [...prev, trimmed])
    setExtraEmailInput('')
  }

  function removeExtraEmail(email: string) {
    setExtraEmails((prev) => prev.filter((e) => e !== email))
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter') {
      e.preventDefault()
      addExtraEmail()
    }
  }

  function handleConfirm() {
    if (!selectedProposalId) return
    if (!name.trim()) return
    setApiError(null)
    finalize(
      {
        proposed_time_id: selectedProposalId,
        name: name.trim(),
        excluded_user_ids: Array.from(excludedUserIds),
        extra_emails: extraEmails,
        note,
        location,
        video_call_link: videoCallLink,
      },
      {
        onSuccess: () => {
          onSuccess()
          onClose()
        },
        onError: (err: unknown) => {
          const detail = (err as { detail?: string })?.detail
          if (detail === 'calendar_create_failed') {
            setApiError('Could not create calendar event — check your calendar connection and try again')
          } else if (detail === 'no_write_calendar') {
            setApiError('No write calendar configured — go to Settings to set one')
          } else {
            setApiError('Something went wrong — please try again')
          }
        },
      }
    )
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-lg shadow-warm-md flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-outline-variant/20 shrink-0">
          <h2 className="text-xl font-bold text-on-surface">Finalize Event</h2>
          <button onClick={onClose} className="p-2 rounded-full hover:bg-surface-container transition-colors">
            <X className="w-5 h-5 text-on-surface-variant" />
          </button>
        </div>

        {/* Scrollable body */}
        <div className="overflow-y-auto flex-1 p-6 space-y-6">
          {/* Event name */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
              Event Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Event name"
              className="w-full bg-surface-container-low rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm font-medium text-on-surface"
            />
          </div>

          {/* Proposal selection */}
          <div className="space-y-2">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
              Select a Time
            </label>
            {proposals.length === 0 ? (
              <p className="text-sm text-on-surface-variant">No proposals available.</p>
            ) : (
              <div className="space-y-2">
                {proposals.map((proposal) => {
                  const start = new Date(proposal.start_time_utc)
                  const end = new Date(proposal.end_time_utc)
                  const dayLabel = start.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
                  const timeRange = `${start.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })} – ${end.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })}`
                  const isSelected = selectedProposalId === proposal.id
                  return (
                    <label
                      key={proposal.id}
                      className={`flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-colors ${
                        isSelected
                          ? 'border-primary bg-primary/8'
                          : 'border-outline-variant/30 bg-surface-container-low hover:bg-surface-container'
                      }`}
                    >
                      <input
                        type="radio"
                        name="proposal"
                        value={proposal.id}
                        checked={isSelected}
                        onChange={() => setSelectedProposalId(proposal.id)}
                        className="mt-0.5 accent-primary"
                      />
                      <div>
                        <p className="text-sm font-bold text-on-surface">{dayLabel}</p>
                        <p className="text-xs text-on-surface-variant">{timeRange}</p>
                        <p className="text-xs text-on-surface-variant mt-0.5">{proposal.reasoning}</p>
                      </div>
                      <span className="ml-auto text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0">
                        #{proposal.rank}
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>

          {/* Attendees checklist */}
          {acceptedParticipants.length > 0 && (
            <div className="space-y-2">
              <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
                Attendees
              </label>
              <div className="space-y-1">
                {acceptedParticipants.map((p) => {
                  const isExcluded = excludedUserIds.has(p.user_id)
                  const isCoord = p.user_id === event.coordinator_id
                  return (
                    <label
                      key={p.user_id}
                      className={`flex items-center gap-3 px-3 py-2 rounded-xl cursor-pointer transition-colors ${
                        isCoord ? 'opacity-60 cursor-not-allowed' : 'hover:bg-surface-container-low'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={!isExcluded}
                        disabled={isCoord}
                        onChange={() => !isCoord && toggleParticipant(p.user_id)}
                        className="accent-primary"
                      />
                      <div className="w-6 h-6 rounded-full bg-surface-container flex items-center justify-center text-[10px] font-bold text-on-surface-variant shrink-0">
                        {(p.full_name ?? p.email_address ?? '?').charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm text-on-surface">{p.full_name ?? p.email_address ?? 'Unknown'}</span>
                      {isCoord && (
                        <span className="ml-auto text-[10px] font-bold text-outline uppercase tracking-wide">organizer</span>
                      )}
                    </label>
                  )
                })}
              </div>

              {/* Extra emails */}
              <div className="space-y-2 pt-1">
                <div className="flex gap-2">
                  <input
                    type="email"
                    value={extraEmailInput}
                    onChange={(e) => setExtraEmailInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Add external guest email"
                    className="flex-1 bg-surface-container-low rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm"
                  />
                  <button
                    onClick={addExtraEmail}
                    className="p-2 rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors"
                  >
                    <Plus className="w-4 h-4 text-on-surface-variant" />
                  </button>
                </div>
                {extraEmails.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {extraEmails.map((email) => (
                      <span
                        key={email}
                        className="flex items-center gap-1 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium"
                      >
                        {email}
                        <button onClick={() => removeExtraEmail(email)} className="hover:text-primary/60">
                          <X className="w-3 h-3" />
                        </button>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Note */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
              Note (optional)
            </label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Add a note to the calendar invite"
              className="w-full bg-surface-container-low rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all resize-none placeholder:text-outline/50 text-sm"
            />
          </div>

          {/* Location */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
              Location (optional)
            </label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              placeholder="Add a location"
              className="w-full bg-surface-container-low rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm"
            />
          </div>

          {/* Video call link */}
          <div className="space-y-1.5">
            <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
              Video Call Link (optional)
            </label>
            <input
              type="url"
              value={videoCallLink}
              onChange={(e) => setVideoCallLink(e.target.value)}
              placeholder="https://meet.google.com/…"
              className="w-full bg-surface-container-low rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-primary-fixed focus:bg-surface-container-lowest transition-all placeholder:text-outline/50 text-sm"
            />
          </div>

          {/* Error */}
          {apiError && (
            <p className="text-sm text-error font-medium">{apiError}</p>
          )}
        </div>

        {/* Sticky footer */}
        <div className="flex gap-3 p-6 border-t border-outline-variant/20 shrink-0">
          <button
            onClick={onClose}
            className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold hover:bg-surface-container transition-colors text-sm"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            disabled={isPending || !selectedProposalId || !name.trim()}
            className="flex-1 py-3 rounded-xl bg-primary text-on-primary font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:-translate-y-0.5 transition-all duration-300 text-sm"
          >
            <CalendarCheck className="w-4 h-4" />
            {isPending ? 'Confirming…' : 'Confirm & Add to Calendar'}
          </button>
        </div>
      </div>
    </div>
  )
}
