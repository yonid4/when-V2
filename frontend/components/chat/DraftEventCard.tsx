'use client'

import { useState } from 'react'
import { Calendar, Clock, Users, ArrowRight, Sparkles } from 'lucide-react'
import type { ChatActionPayload, ChatButton, DraftCard } from '@/types'
import { formatDateWindowWithYear, formatDayLabel, formatTime } from '@/lib/dates'

interface DraftEventCardProps {
  card: DraftCard
  buttons: ChatButton[]
  disabled: boolean
  onAction: (action: ChatActionPayload) => void
}

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).replace(/_/g, ' ')
}

function formatChangeValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

/**
 * Inline draft summary card rendered in the chat drawer. Mirrors FinalizeCard's
 * visual language but lives inline (no modal overlay). Handles create modes
 * (with a radio slot list in `create_direct`) and edit mode (before → after
 * change rows). Action buttons echo their structured `action` verbatim; the
 * Confirm button in `create_direct` mode additionally carries the selected
 * `slot_index`.
 */
export function DraftEventCard({ card, buttons, disabled, onAction }: DraftEventCardProps) {
  const [selectedSlotIndex, setSelectedSlotIndex] = useState(0)

  const isEdit = card.mode === 'edit'
  const showSlots = card.mode === 'create_direct' && card.slots.length > 0

  function handleButtonClick(button: ChatButton) {
    if (disabled) return
    if (card.mode === 'create_direct' && button.action.type === 'confirm_draft') {
      onAction({ ...button.action, slot_index: selectedSlotIndex })
      return
    }
    onAction(button.action)
  }

  return (
    <div className="bg-surface-container-lowest rounded-2xl border border-outline-variant/30 shadow-sm overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-outline-variant/20 flex items-center gap-2">
        <Sparkles className="w-4 h-4 text-primary shrink-0" />
        <span className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
          {isEdit ? 'Proposed changes' : 'Draft event'}
        </span>
      </div>

      <div className="p-4 space-y-4">
        {isEdit ? (
          <EditChanges card={card} />
        ) : (
          <>
            {/* Title + type badge */}
            <div className="space-y-2">
              <h3 className="text-lg font-extrabold font-headline text-on-surface leading-tight">
                {card.title}
              </h3>
              {card.event_type && (
                <span className="inline-block px-2.5 py-0.5 bg-secondary-container text-on-secondary-container text-[10px] font-bold uppercase tracking-wider rounded-full">
                  {titleCase(card.event_type)}
                </span>
              )}
            </div>

            {/* Window + duration */}
            <div className="space-y-1.5">
              {card.earliest_datetime_utc && card.latest_datetime_utc && (
                <div className="flex items-center gap-2 text-on-surface-variant">
                  <Calendar className="w-4 h-4 text-primary shrink-0" />
                  <span className="text-xs font-medium">
                    {formatDateWindowWithYear(card.earliest_datetime_utc, card.latest_datetime_utc)}
                  </span>
                </div>
              )}
              {card.duration_minutes != null && (
                <div className="flex items-center gap-2 text-on-surface-variant">
                  <Clock className="w-4 h-4 text-primary shrink-0" />
                  <span className="text-xs font-medium">{card.duration_minutes} min</span>
                </div>
              )}
            </div>

            {/* Participants */}
            {card.participants.length > 0 && (
              <div className="space-y-1.5">
                <div className="flex items-center gap-2 text-outline">
                  <Users className="w-4 h-4 shrink-0" />
                  <span className="text-[10px] font-extrabold uppercase tracking-[0.15em]">
                    Participants ({card.participants.length})
                  </span>
                </div>
                <ul className="space-y-1">
                  {card.participants.map((participant) => (
                    <li
                      key={participant.email}
                      className="flex items-center gap-2 text-sm text-on-surface"
                    >
                      <span className="truncate">{participant.name ?? participant.email}</span>
                      <span className="ml-auto flex items-center gap-1 shrink-0">
                        {participant.in_system && (
                          <span className="px-1.5 py-0.5 rounded-full bg-primary/10 text-primary text-[9px] font-bold uppercase tracking-wide">
                            In app
                          </span>
                        )}
                        {participant.has_calendar && (
                          <span className="px-1.5 py-0.5 rounded-full bg-secondary-container text-on-secondary-container text-[9px] font-bold uppercase tracking-wide">
                            Calendar
                          </span>
                        )}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Slot radio list (direct mode only) */}
            {showSlots && (
              <div className="space-y-2">
                <span className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
                  Pick a time
                </span>
                <div className="space-y-2">
                  {card.slots.map((slot, index) => {
                    const isSelected = selectedSlotIndex === index
                    return (
                      <label
                        key={`${slot.start_time_utc}-${index}`}
                        className={`flex items-start gap-2.5 p-2.5 rounded-xl border cursor-pointer transition-colors ${
                          isSelected
                            ? 'border-primary bg-primary/8'
                            : 'border-outline-variant/30 bg-surface-container-low hover:bg-surface-container'
                        }`}
                      >
                        <input
                          type="radio"
                          name="draft-slot"
                          value={index}
                          checked={isSelected}
                          disabled={disabled}
                          onChange={() => setSelectedSlotIndex(index)}
                          className="mt-0.5 accent-primary"
                        />
                        <div className="min-w-0">
                          <p className="text-sm font-bold text-on-surface">
                            {formatDayLabel(slot.start_time_utc)}
                          </p>
                          <p className="text-xs text-on-surface-variant">
                            {formatTime(slot.start_time_utc)} – {formatTime(slot.end_time_utc)}
                          </p>
                          <p className="text-[11px] text-on-surface-variant mt-0.5">
                            {slot.free_count}/{slot.total} free
                            {slot.conflict_count > 0 ? ` · ${slot.conflict_count} conflict${slot.conflict_count === 1 ? '' : 's'}` : ''}
                          </p>
                          {slot.reasoning && (
                            <p className="text-[11px] text-on-surface-variant mt-0.5">{slot.reasoning}</p>
                          )}
                        </div>
                      </label>
                    )
                  })}
                </div>
              </div>
            )}
          </>
        )}

        {/* Action buttons */}
        {buttons.length > 0 && (
          <div className="flex flex-wrap gap-2 pt-1">
            {buttons.map((button) => {
              const isCancel = button.action.type === 'cancel'
              return (
                <button
                  key={`${button.action.type}-${button.label}`}
                  type="button"
                  onClick={() => handleButtonClick(button)}
                  disabled={disabled}
                  className={`flex-1 min-w-[96px] py-2.5 px-3 rounded-xl text-sm font-bold transition-colors disabled:opacity-60 ${
                    isCancel
                      ? 'border border-outline-variant text-on-surface-variant hover:bg-surface-container'
                      : 'bg-primary text-on-primary hover:bg-primary/90'
                  }`}
                >
                  {button.label}
                </button>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

function EditChanges({ card }: { card: DraftCard }) {
  const changes = card.changes ?? []

  return (
    <div className="space-y-3">
      {card.title && (
        <h3 className="text-lg font-extrabold font-headline text-on-surface leading-tight">
          {card.title}
        </h3>
      )}
      {changes.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No changes to apply.</p>
      ) : (
        <ul className="space-y-2">
          {changes.map((change) => (
            <li
              key={change.field}
              className="rounded-xl border border-outline-variant/30 bg-surface-container-low p-2.5"
            >
              <p className="text-[10px] font-extrabold text-outline uppercase tracking-[0.15em] mb-1">
                {change.label}
              </p>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-on-surface-variant line-through decoration-outline/50">
                  {formatChangeValue(change.from)}
                </span>
                <ArrowRight className="w-3.5 h-3.5 text-primary shrink-0" />
                <span className="font-bold text-on-surface">{formatChangeValue(change.to)}</span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
