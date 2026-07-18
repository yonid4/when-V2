/**
 * Package 7 (chat UI) — DraftEventCard tests
 *
 * Covers:
 * - create fixture (create_direct): selecting a slot then Confirm posts the
 *   structured action { type: 'confirm_draft', slot_index }
 * - Cancel posts { type: 'cancel' } verbatim
 * - edit fixture renders before → after change rows
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

import { DraftEventCard } from '@/components/chat/DraftEventCard'
import type { ChatActionPayload, ChatButton, DraftCard } from '@/types'

function makeCreateCard(overrides: Partial<DraftCard> = {}): DraftCard {
  return {
    mode: 'create_direct',
    title: 'Team Lunch',
    event_type: 'social',
    earliest_datetime_utc: '2026-04-10T09:00:00.000Z',
    latest_datetime_utc: '2026-04-17T17:00:00.000Z',
    duration_minutes: 60,
    participants: [
      { name: 'Alice', email: 'alice@example.com', in_system: true, has_calendar: true, user_id: 'u1' },
      { name: null, email: 'bob@example.com', in_system: false, has_calendar: false, user_id: null },
    ],
    slots: [
      {
        start_time_utc: '2026-04-10T12:00:00.000Z',
        end_time_utc: '2026-04-10T13:00:00.000Z',
        conflict_count: 0,
        free_count: 3,
        total: 3,
        reasoning: 'Everyone is free',
      },
      {
        start_time_utc: '2026-04-11T14:00:00.000Z',
        end_time_utc: '2026-04-11T15:00:00.000Z',
        conflict_count: 1,
        free_count: 2,
        total: 3,
        reasoning: 'One person busy',
      },
    ],
    changes: null,
    event_uid: null,
    ...overrides,
  }
}

const createButtons: ChatButton[] = [
  { label: 'Confirm', action: { type: 'confirm_draft' } },
  { label: 'Cancel', action: { type: 'cancel' } },
]

describe('DraftEventCard — create mode', () => {
  let onAction: ReturnType<typeof vi.fn<(action: ChatActionPayload) => void>>

  beforeEach(() => {
    onAction = vi.fn<(action: ChatActionPayload) => void>()
  })

  it('renders the title, type badge and participants', () => {
    render(
      <DraftEventCard card={makeCreateCard()} buttons={createButtons} disabled={false} onAction={onAction} />
    )
    expect(screen.getByText('Team Lunch')).toBeInTheDocument()
    expect(screen.getByText('Social')).toBeInTheDocument()
    expect(screen.getByText('Alice')).toBeInTheDocument()
    expect(screen.getByText('bob@example.com')).toBeInTheDocument()
  })

  it('selecting a slot then Confirm posts { type: confirm_draft, slot_index }', () => {
    render(
      <DraftEventCard card={makeCreateCard()} buttons={createButtons} disabled={false} onAction={onAction} />
    )

    const radios = screen.getAllByRole('radio')
    expect(radios).toHaveLength(2)

    // Select the second slot (index 1).
    fireEvent.click(radios[1])
    fireEvent.click(screen.getByText('Confirm'))

    expect(onAction).toHaveBeenCalledTimes(1)
    expect(onAction).toHaveBeenCalledWith({ type: 'confirm_draft', slot_index: 1 })
  })

  it('Confirm without changing selection uses the default slot index 0', () => {
    render(
      <DraftEventCard card={makeCreateCard()} buttons={createButtons} disabled={false} onAction={onAction} />
    )
    fireEvent.click(screen.getByText('Confirm'))
    expect(onAction).toHaveBeenCalledWith({ type: 'confirm_draft', slot_index: 0 })
  })

  it('Cancel posts the { type: cancel } action verbatim', () => {
    render(
      <DraftEventCard card={makeCreateCard()} buttons={createButtons} disabled={false} onAction={onAction} />
    )
    fireEvent.click(screen.getByText('Cancel'))
    expect(onAction).toHaveBeenCalledWith({ type: 'cancel' })
  })

  it('does not fire actions while disabled', () => {
    render(
      <DraftEventCard card={makeCreateCard()} buttons={createButtons} disabled={true} onAction={onAction} />
    )
    fireEvent.click(screen.getByText('Confirm'))
    expect(onAction).not.toHaveBeenCalled()
  })
})

describe('DraftEventCard — edit mode', () => {
  const editCard: DraftCard = {
    mode: 'edit',
    title: 'Team Lunch',
    event_type: null,
    earliest_datetime_utc: null,
    latest_datetime_utc: null,
    duration_minutes: null,
    participants: [],
    slots: [],
    changes: [
      { field: 'title', label: 'Title', from: 'Team Lunch', to: 'Team Dinner' },
      { field: 'duration_minutes', label: 'Duration', from: 60, to: 90 },
    ],
    event_uid: 'evt-1',
  }

  it('renders before → after change rows', () => {
    render(<DraftEventCard card={editCard} buttons={createButtons} disabled={false} onAction={vi.fn()} />)

    // Change labels
    expect(screen.getByText('Title')).toBeInTheDocument()
    expect(screen.getByText('Duration')).toBeInTheDocument()

    // Before values (from) and after values (to)
    expect(screen.getByText('Team Dinner')).toBeInTheDocument()
    expect(screen.getByText('60')).toBeInTheDocument()
    expect(screen.getByText('90')).toBeInTheDocument()

    // No slot radios in edit mode
    expect(screen.queryAllByRole('radio')).toHaveLength(0)
  })
})
