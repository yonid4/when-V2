'use client'

import type { ProposedTime } from '@/types'
import { formatSlotTime } from '@/lib/dates'

const ROW_HEIGHT_PX = 32 // must match AvailabilityGrid scrollable h-8

// Tertiary-fixed is the "warm amber" token — #ffdcc4 — used as the BEST TIME color
// (matches the tertiary palette in globals.css)
const BEST_BG = 'color-mix(in srgb, var(--color-tertiary-fixed) 60%, transparent)'
const BEST_TEXT = 'var(--color-on-tertiary-fixed)'
const BEST_TEXT_DIM = 'var(--color-on-tertiary-fixed-variant)'

interface SlotWithOffset {
  proposal: ProposedTime
  colIndex: number
  startRow: number
  rowsSpanned: number
  offsetIndex: number
  groupSize: number
}

function buildSlotsWithOffsets(
  proposals: ProposedTime[],
  columnDates: Date[],
  startHour: number,
): SlotWithOffset[] {
  // Bucket proposals by column index
  const byCol: Map<number, Array<{ proposal: ProposedTime; startRow: number; rowsSpanned: number }>> = new Map()

  for (const proposal of proposals) {
    const slotStart = new Date(proposal.start_time_utc)
    const slotEnd = new Date(proposal.end_time_utc)

    const colIndex = columnDates.findIndex(
      (d) =>
        d.getFullYear() === slotStart.getFullYear() &&
        d.getMonth() === slotStart.getMonth() &&
        d.getDate() === slotStart.getDate(),
    )
    if (colIndex === -1) continue

    const startMinutes = (slotStart.getHours() - startHour) * 60 + slotStart.getMinutes()
    const endMinutes = (slotEnd.getHours() - startHour) * 60 + slotEnd.getMinutes()
    const startRow = startMinutes / 30
    const rowsSpanned = (endMinutes - startMinutes) / 30

    if (!byCol.has(colIndex)) byCol.set(colIndex, [])
    byCol.get(colIndex)!.push({ proposal, startRow, rowsSpanned })
  }

  const result: SlotWithOffset[] = []

  for (const [colIndex, slots] of byCol.entries()) {
    // Sort by rank so lower rank (better) gets offsetIndex 0
    const sorted = [...slots].sort((a, b) => a.proposal.rank - b.proposal.rank)

    // Assign offsetIndex: for each slot, count how many higher-ranked slots it overlaps with
    const withOffset = sorted.map((slot, i) => {
      let offsetIndex = 0
      for (let j = 0; j < i; j++) {
        const other = sorted[j]
        const overlaps =
          slot.startRow < other.startRow + other.rowsSpanned &&
          slot.startRow + slot.rowsSpanned > other.startRow
        if (overlaps) offsetIndex++
      }

      // Determine group size (how many total slots overlap this one, including itself)
      let groupSize = 1
      for (let j = 0; j < sorted.length; j++) {
        if (j === i) continue
        const other = sorted[j]
        const overlaps =
          slot.startRow < other.startRow + other.rowsSpanned &&
          slot.startRow + slot.rowsSpanned > other.startRow
        if (overlaps) groupSize++
      }

      return { proposal: slot.proposal, colIndex, startRow: slot.startRow, rowsSpanned: slot.rowsSpanned, offsetIndex, groupSize }
    })

    result.push(...withOffset)
  }

  return result
}

interface Props {
  proposals: ProposedTime[]
  visible: boolean
  eventStart: Date    // Date whose .getHours() gives the grid's first hour
  columnDates: Date[] // the 7 column dates rendered by the grid, in order
  isScrollable: boolean
  totalRows: number
}

export function ProposedTimeOverlay({ proposals, visible, eventStart, columnDates, isScrollable, totalRows }: Props) {
  if (!visible || proposals.length === 0) return null

  const startHour = eventStart.getHours()
  const slots = buildSlotsWithOffsets(proposals, columnDates, startHour)

  return (
    <>
      {slots.map(({ proposal, colIndex, startRow, rowsSpanned, offsetIndex, groupSize }) => {
        const top = isScrollable
          ? startRow * ROW_HEIGHT_PX + 2
          : `calc(${(startRow / totalRows) * 100}% + 2px)`
        const height = isScrollable
          ? rowsSpanned * ROW_HEIGHT_PX - 4
          : `calc(${(rowsSpanned / totalRows) * 100}% - 4px)`
        const isOverlapping = groupSize > 1
        const marginLeft = offsetIndex * 12

        const slotStart = new Date(proposal.start_time_utc)
        const slotEnd = new Date(proposal.end_time_utc)
        const durationMs = slotEnd.getTime() - slotStart.getTime()
        const showLabel = durationMs >= 30 * 60 * 1000

        return (
          <div
            key={proposal.id}
            style={{
              position: 'absolute',
              top,
              height,
              left: `calc(${colIndex} * (100% / 7) + ${marginLeft}px)`,
              width: `calc(100% / 7 * 1 - ${marginLeft}px)`,
              pointerEvents: 'none',
              zIndex: 30 - offsetIndex,
            }}
          >
            <div
              className="absolute inset-x-0.5 rounded-md overflow-hidden flex flex-col items-center justify-center gap-0.5"
              style={{
                top: 0,
                height: '100%',
                backgroundColor: BEST_BG,
                boxShadow: isOverlapping
                  ? '0 1px 4px rgba(0,0,0,0.15), inset 0 0 0 1px rgba(142,78,20,0.25)'
                  : '0 1px 3px rgba(0,0,0,0.10)',
              }}
            >
              <span
                className="text-[11px] font-black leading-none select-none"
                style={{ color: BEST_TEXT }}
              >
                ✦ #{proposal.rank}
              </span>
              {showLabel && (
                <span
                  className="text-[10px] font-semibold leading-none select-none"
                  style={{ color: BEST_TEXT_DIM }}
                >
                  {formatSlotTime(proposal.start_time_utc)}–{formatSlotTime(proposal.end_time_utc)}
                </span>
              )}
            </div>
          </div>
        )
      })}
    </>
  )
}
