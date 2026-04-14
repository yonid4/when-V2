'use client'

import type { ProposalResponse } from '@/types'
import { formatSlotTime } from '@/lib/dates'

const ROW_HEIGHT_PX = 32 // must match AvailabilityGrid scrollable row height (h-8)

interface Props {
  proposals: ProposalResponse[]
  visible: boolean
  eventStart: Date       // earliest hour shown in the grid (used to compute row offset)
  columnDates: Date[]    // the 7 column dates rendered by the grid, in order
  isScrollable: boolean  // true when grid uses fixed px rows, false when percentage-based
  totalRows: number      // total number of 30-min rows in the grid (totalHours * 2)
}

export function ProposedTimeOverlay({ proposals, visible, eventStart, columnDates, isScrollable, totalRows }: Props) {
  if (!visible) return null

  const startHour = eventStart.getHours()

  return (
    <>
      {proposals.map((proposal) => {
        const slotStart = new Date(proposal.start_time_utc)
        const slotEnd = new Date(proposal.end_time_utc)

        // Find which column this proposal falls on
        const colIndex = columnDates.findIndex(
          (d) =>
            d.getFullYear() === slotStart.getFullYear() &&
            d.getMonth() === slotStart.getMonth() &&
            d.getDate() === slotStart.getDate()
        )
        if (colIndex === -1) return null

        const startMinutes = (slotStart.getHours() - startHour) * 60 + slotStart.getMinutes()
        const endMinutes = (slotEnd.getHours() - startHour) * 60 + slotEnd.getMinutes()
        const startRow = startMinutes / 30
        const rowsSpanned = (endMinutes - startMinutes) / 30

        const topStyle = isScrollable
          ? startRow * ROW_HEIGHT_PX + 2
          : `calc(${(startRow / totalRows) * 100}% + 2px)`
        const heightStyle = isScrollable
          ? rowsSpanned * ROW_HEIGHT_PX - 4
          : `calc(${(rowsSpanned / totalRows) * 100}% - 4px)`

        const durationMs = slotEnd.getTime() - slotStart.getTime()
        const showLabel = durationMs >= 30 * 60 * 1000

        return (
          <div
            key={proposal.id}
            data-col={colIndex}
            style={{
              position: 'absolute',
              top: topStyle,
              height: heightStyle,
              left: `calc(${colIndex} * (100% / 7))`,
              width: 'calc(100% / 7)',
              pointerEvents: 'none',
              zIndex: 30,
            }}
          >
            <div
              className="absolute inset-x-0.5 rounded-md overflow-hidden flex flex-col items-center justify-center gap-0.5"
              style={{
                top: 0,
                height: '100%',
                backgroundColor: 'color-mix(in srgb, var(--color-tertiary-fixed) 45%, transparent)',
              }}
            >
              <span className="text-[11px] font-black leading-none" style={{ color: 'var(--color-on-tertiary-fixed)' }}>
                ✦ #{proposal.rank}
              </span>
              {showLabel && (
                <span className="text-[10px] font-semibold leading-none" style={{ color: 'var(--color-on-tertiary-fixed-variant)' }}>
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
