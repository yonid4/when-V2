'use client'

import { formatSlotTime } from '@/lib/dates'

const ROW_HEIGHT_PX = 32 // must match AvailabilityGrid scrollable h-8

interface Props {
  startTimeUtc: string
  endTimeUtc: string
  eventStart: Date
  columnDates: Date[]
  isScrollable: boolean
  totalRows: number
}

export function FinalizedSlotOverlay({
  startTimeUtc,
  endTimeUtc,
  eventStart,
  columnDates,
  isScrollable,
  totalRows,
}: Props) {
  const slotStart = new Date(startTimeUtc)
  const slotEnd = new Date(endTimeUtc)
  const startHour = eventStart.getHours()

  const colIndex = columnDates.findIndex(
    (d) =>
      d.getFullYear() === slotStart.getFullYear() &&
      d.getMonth() === slotStart.getMonth() &&
      d.getDate() === slotStart.getDate(),
  )
  if (colIndex === -1) return null

  const startMinutes = (slotStart.getHours() - startHour) * 60 + slotStart.getMinutes()
  const endMinutes = (slotEnd.getHours() - startHour) * 60 + slotEnd.getMinutes()
  const startRow = startMinutes / 30
  const rowsSpanned = (endMinutes - startMinutes) / 30

  const top = isScrollable
    ? startRow * ROW_HEIGHT_PX + 2
    : `calc(${(startRow / totalRows) * 100}% + 2px)`
  const height = isScrollable
    ? rowsSpanned * ROW_HEIGHT_PX - 4
    : `calc(${(rowsSpanned / totalRows) * 100}% - 4px)`

  const durationMs = slotEnd.getTime() - slotStart.getTime()
  const showTime = durationMs >= 30 * 60 * 1000

  return (
    <div
      style={{
        position: 'absolute',
        top,
        height,
        left: `calc(${colIndex} * (100% / 7))`,
        width: 'calc(100% / 7)',
        pointerEvents: 'none',
        zIndex: 35,
      }}
    >
      <div
        className="absolute inset-x-0.5 rounded-md overflow-hidden flex flex-col items-center justify-center gap-0.5"
        style={{
          top: 0,
          height: '100%',
          backgroundColor: 'color-mix(in srgb, var(--color-primary) 30%, transparent)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.15), inset 0 0 0 2px color-mix(in srgb, var(--color-primary) 70%, transparent)',
        }}
      >
        <span
          className="text-[11px] font-black leading-none select-none"
          style={{ color: 'var(--color-primary)' }}
        >
          ✓ Confirmed
        </span>
        {showTime && (
          <span
            className="text-[10px] font-semibold leading-none select-none"
            style={{ color: 'var(--color-on-primary-container)' }}
          >
            {formatSlotTime(startTimeUtc)}–{formatSlotTime(endTimeUtc)}
          </span>
        )}
      </div>
    </div>
  )
}
