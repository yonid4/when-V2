'use client'

import { useState } from 'react'
import type { PreferredSlot, AvailabilitySegment, PendingSlot } from '@/types'
import {
  busyIntensityClass,
  preferredIntensityClass,
  clipToGridBounds,
} from '@/lib/gridUtils'
import { toDate, formatSlotTime } from '@/lib/dates'

export function AvailabilityGrid({
  segments,
  preferredSlots,
  startDate,
  earliestTime,
  latestTime,
  isEditMode,
  eventStatus,
  pendingSlot,
  currentUserId,
  deletingSlotId,
  slotsToDelete,
  onCellMouseDown,
  onCellMouseEnter,
  onPendingSlotEdgeMouseDown,
  onSlotClick,
  onSlotDeleteConfirm,
  onSlotDeleteCancel,
}: {
  segments: AvailabilitySegment[]
  preferredSlots: PreferredSlot[]
  startDate: string
  earliestTime: string
  latestTime: string
  isEditMode: boolean
  eventStatus: string
  pendingSlot: PendingSlot | null
  currentUserId: string
  deletingSlotId: string | null
  slotsToDelete: string[]
  onCellMouseDown: (dayIndex: number, rowIndex: number, cellStartUtc: Date) => void
  onCellMouseEnter: (dayIndex: number, rowIndex: number, cellStartUtc: Date) => void
  onPendingSlotEdgeMouseDown: (edge: 'top' | 'bottom', e: React.MouseEvent) => void
  onSlotClick: (slotId: string) => void
  onSlotDeleteConfirm: (slotId: string) => void
  onSlotDeleteCancel: () => void
}) {
  const earliestDate = toDate(earliestTime)
  const latestDate = toDate(latestTime)
  const startHour = earliestDate.getHours()
  const latestHour = latestDate.getHours()
  const latestMinute = latestDate.getMinutes()
  const endHour = latestMinute > 0 ? latestHour + 1 : latestHour
  const totalHours = endHour - startHour

  const hours = Array.from({ length: totalHours }, (_, i) => {
    const h = startHour + i
    const period = h < 12 ? 'AM' : 'PM'
    const display = h % 12 === 0 ? 12 : h % 12
    return `${String(display).padStart(2, '0')}:00 ${period}`
  })

  const isScrollable = totalHours > 8
  const DAY_NAMES = ['SUN', 'MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']

  const [weekOffset, setWeekOffset] = useState(0)

  const baseDate = toDate(startDate)
  const dayOfWeek = baseDate.getDay()
  const offsetToMonday = (dayOfWeek + 6) % 7
  baseDate.setDate(baseDate.getDate() - offsetToMonday + weekOffset * 7)

  const days = Array.from({ length: 7 }, (_, i) => {
    const d = new Date(baseDate)
    d.setDate(d.getDate() + i)
    return {
      label: DAY_NAMES[d.getDay()],
      date: d.getDate(),
      month: d.toLocaleString('en-US', { month: 'short' }),
      year: d.getFullYear(),
    }
  })

  const firstDay = days[0]
  const lastDay = days[6]
  const monthLabel = firstDay.month === lastDay.month
    ? `${firstDay.month} ${firstDay.year}`
    : `${firstDay.month} – ${lastDay.month} ${lastDay.year}`

  // Total half-rows per day column
  const totalRows = totalHours * 2

  return (
    <div className="flex-1 min-h-0 flex flex-col overflow-hidden bg-surface-container-lowest rounded-xl shadow-[0_20px_40px_-15px_rgba(155,68,40,0.05)]">
      {/* Grid card header: week nav + edit button */}
      <div className="flex items-center justify-between px-6 pt-5 pb-3 shrink-0">
        <button
          onClick={() => setWeekOffset((o) => o - 1)}
          className="p-1.5 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant"
          aria-label="Previous week"
        >
          <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <span className="text-xs font-bold text-on-surface-variant uppercase tracking-widest">{monthLabel}</span>

        <div className="flex items-center gap-2">
          {isEditMode && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-primary/30 bg-primary/5">
              <div className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="text-xs font-bold text-primary">Editing…</span>
            </div>
          )}
          <button
            onClick={() => setWeekOffset((o) => o + 1)}
            className="p-1.5 rounded-lg hover:bg-surface-container transition-colors text-on-surface-variant"
            aria-label="Next week"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 18l6-6-6-6" />
            </svg>
          </button>
        </div>
      </div>

      {/* Day headers */}
      <div className="grid grid-cols-[80px_1fr] border-b border-outline-variant/25 shrink-0 mx-6">
        <div className="h-12 border-r border-outline-variant/25" />
        <div className="grid grid-cols-7 h-12">
          {days.map((d, i) => (
            <div
              key={i}
              className={`flex items-center justify-center font-bold text-on-surface-variant/80 uppercase text-[10px] tracking-widest ${i < 6 ? 'border-r border-outline-variant/25' : ''}`}
            >
              {d.label} {d.date}
            </div>
          ))}
        </div>
      </div>

      {/* Grid body */}
      <div className={`flex flex-col flex-1 min-h-0 mx-6 mb-6 ${isScrollable ? 'overflow-y-auto' : 'overflow-hidden'}`}>
        <div className={`flex flex-row ${isScrollable ? '' : 'flex-1 min-h-0'}`}>
          {/* Time labels */}
          <div className="w-[80px] shrink-0 flex flex-col">
            {hours.map((h) => (
              <div key={h} className={`flex items-start justify-center pt-1 ${isScrollable ? 'h-16' : 'flex-1'}`}>
                <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-widest">{h}</span>
              </div>
            ))}
          </div>

          {/* Grid cells */}
          <div className={`flex-1 flex flex-col ${isScrollable ? '' : 'min-h-0'}`}>
            <div className={`grid grid-cols-7 ${isScrollable ? '' : 'flex-1 min-h-0'}`}>
              {days.map((_day, di) => {
                const colDate = new Date(baseDate)
                colDate.setDate(colDate.getDate() + di)

                // ── Overlay geometry helper ──────────────────────────────────
                const ROW_HEIGHT_PX = 32 // h-8 when scrollable
                function overlayStyle(slotStartUtc: Date, slotEndUtc: Date): React.CSSProperties {
                  const startMinutes = (slotStartUtc.getHours() - startHour) * 60 + slotStartUtc.getMinutes()
                  const endMinutes = (slotEndUtc.getHours() - startHour) * 60 + slotEndUtc.getMinutes()
                  const startRow = startMinutes / 30
                  const rowsSpanned = (endMinutes - startMinutes) / 30
                  if (isScrollable) {
                    return { position: 'absolute', left: 0, right: 0, pointerEvents: 'none', top: startRow * ROW_HEIGHT_PX + 2, height: rowsSpanned * ROW_HEIGHT_PX - 4 }
                  }
                  const topPct = (startRow / totalRows) * 100
                  const heightPct = (rowsSpanned / totalRows) * 100
                  return { position: 'absolute', left: 0, right: 0, pointerEvents: 'none', top: `calc(${topPct}% + 2px)`, height: `calc(${heightPct}% - 4px)` }
                }

                // ── Slot overlays for this column ────────────────────────────
                const colDayStart = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), startHour, 0)
                const colDayEnd = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), endHour, 0)

                const colSegmentsByType = segments.reduce<Record<string, AvailabilitySegment[]>>(
                  (acc, s) => {
                    const ss = toDate(s.start_time_utc); const se = toDate(s.end_time_utc)
                    if (ss < colDayEnd && se > colDayStart) {
                      acc[s.type] = acc[s.type] ?? []
                      acc[s.type].push(s)
                    }
                    return acc
                  },
                  {}
                )
                const colPreferred = preferredSlots.filter((s) => {
                  const ss = toDate(s.start_time_utc); const se = toDate(s.end_time_utc)
                  return ss < colDayEnd && se > colDayStart
                })


                // ── Pending slot overlay ─────────────────────────────────────
                const colPending = pendingSlot !== null && pendingSlot.dayIndex === di ? pendingSlot : null
                const pendingOverlayStyle = colPending ? overlayStyle(colPending.startUtc, colPending.endUtc) : null

                return (
                  <div
                    key={di}
                    className={`flex flex-col relative ${isScrollable ? '' : 'flex-1'} ${di < 6 ? 'border-r border-outline-variant/25' : ''}`}
                    onClick={() => { if (deletingSlotId) onSlotDeleteCancel() }}
                  >
                    {Array.from({ length: totalHours }, (_, hi) => {
                      const hour = startHour + hi
                      return [0, 1].map((half) => {
                        const rowIndex = hi * 2 + half
                        const cellStartUtc = new Date(colDate.getFullYear(), colDate.getMonth(), colDate.getDate(), hour, half === 0 ? 0 : 30)
                        const halfClass = isScrollable ? 'h-8' : 'flex-1'

                        return (
                          <div
                            key={`${hi}-${half}`}
                            className={`border-b border-outline-variant/20 transition-colors ${halfClass} ${
                              isEditMode
                                ? 'cursor-crosshair hover:bg-secondary/10'
                                : 'hover:bg-surface-container-high cursor-pointer'
                            }`}
                            onMouseDown={isEditMode ? () => onCellMouseDown(di, rowIndex, cellStartUtc) : undefined}
                            onMouseEnter={isEditMode ? () => onCellMouseEnter(di, rowIndex, cellStartUtc) : undefined}
                          />
                        )
                      })
                    })}

                    {/* Conflict overlays */}
                    {(colSegmentsByType['conflict'] ?? []).map((s, ci) => {
                      const ss = toDate(s.start_time_utc); const se = toDate(s.end_time_utc)
                      const cc = clipToGridBounds(ss, se, colDayStart, colDayEnd)
                      if (cc.endUtc <= cc.startUtc) return null
                      return (
                        <div
                          key={`conflict-${ci}`}
                          style={overlayStyle(cc.startUtc, cc.endUtc)}
                          className="rounded-md z-20 overflow-hidden relative"
                        >
                          <div className="flex w-full h-full">
                            <div className={`w-1/2 h-full ${busyIntensityClass(s.busy_count)}`} />
                            <div className={`w-1/2 h-full ${preferredIntensityClass(s.preferred_count)}`} />
                            <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5">
                              <span className="text-xs font-semibold text-error">CONFLICT</span>
                              {cc.endUtc.getTime() - cc.startUtc.getTime() >= 30 * 60 * 1000 && (
                                <span className="text-xs text-gray-600">{formatSlotTime(cc.startUtc.toISOString())} – {formatSlotTime(cc.endUtc.toISOString())}</span>
                              )}
                            </div>
                          </div>
                        </div>
                      )
                    })}

                    {/* Busy overlays */}
                    {(colSegmentsByType['busy'] ?? []).map((s, bi) => {
                      const ss = toDate(s.start_time_utc); const se = toDate(s.end_time_utc)
                      const cs = clipToGridBounds(ss, se, colDayStart, colDayEnd)
                      if (cs.endUtc <= cs.startUtc) return null
                      return (
                        <div
                          key={`busy-${bi}`}
                          style={overlayStyle(cs.startUtc, cs.endUtc)}
                          className={`${busyIntensityClass(s.busy_count)} rounded-md z-10 overflow-hidden flex items-center justify-center`}
                        >
                          {cs.endUtc.getTime() - cs.startUtc.getTime() >= 30 * 60 * 1000 && (
                            <span className="text-xs text-error font-medium">{formatSlotTime(cs.startUtc.toISOString())} – {formatSlotTime(cs.endUtc.toISOString())}</span>
                          )}
                        </div>
                      )
                    })}

                    {/* Preferred overlays */}
                    {(colSegmentsByType['preferred'] ?? []).map((s, pi) => {
                      const ss = toDate(s.start_time_utc); const se = toDate(s.end_time_utc)
                      const cs = clipToGridBounds(ss, se, colDayStart, colDayEnd)
                      if (cs.endUtc <= cs.startUtc) return null
                      return (
                        <div
                          key={`preferred-${pi}`}
                          style={overlayStyle(cs.startUtc, cs.endUtc)}
                          className={`${preferredIntensityClass(s.preferred_count)} rounded-md z-10 overflow-hidden flex items-center justify-center`}
                        >
                          {cs.endUtc.getTime() - cs.startUtc.getTime() >= 30 * 60 * 1000 && (
                            <span className="text-xs text-secondary font-medium">{formatSlotTime(cs.startUtc.toISOString())} – {formatSlotTime(cs.endUtc.toISOString())}</span>
                          )}
                        </div>
                      )
                    })}

                    {/* Own slot dot indicators — one per own preferred slot */}
                    {colPreferred
                      .filter((s) => s.user_id === currentUserId && !slotsToDelete.includes(s.id))
                      .map((s) => {
                        const clipped = clipToGridBounds(toDate(s.start_time_utc), toDate(s.end_time_utc), colDayStart, colDayEnd)
                        if (clipped.endUtc <= clipped.startUtc) return null
                        return (
                          <div
                            key={`own-dot-${s.id}`}
                            style={{ ...overlayStyle(clipped.startUtc, clipped.endUtc), pointerEvents: 'none', zIndex: 15 }}
                            className="relative"
                          >
                            <div className="absolute bg-secondary rounded-full" style={{ top: 4, right: 6, width: 8, height: 8 }} />
                          </div>
                        )
                      })
                    }

                    {/* Own preferred slot click/delete overlays — only in edit mode and not confirmed */}
                    {isEditMode && eventStatus !== 'confirmed' && colPreferred
                      .filter((s) => s.user_id === currentUserId && !slotsToDelete.includes(s.id))
                      .map((s) => {
                        const isConfirming = deletingSlotId === s.id
                        const clipped = clipToGridBounds(toDate(s.start_time_utc), toDate(s.end_time_utc), colDayStart, colDayEnd)
                        if (clipped.endUtc <= clipped.startUtc) return null
                        const slotStart = clipped.startUtc
                        const slotEnd = clipped.endUtc
                        return (
                          <div
                            key={`own-preferred-${s.id}`}
                            style={{ ...overlayStyle(slotStart, slotEnd), pointerEvents: 'auto', zIndex: 25 }}
                            className="rounded-md cursor-pointer relative flex items-center justify-center"
                            onClick={(e) => { e.stopPropagation(); onSlotClick(s.id) }}
                          >
                            {isConfirming && (
                              <div
                                className="absolute inset-0 flex flex-col items-center justify-center gap-1 bg-surface-container-lowest/95 rounded-md z-30 px-1"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <span className="text-[10px] font-bold text-on-surface text-center leading-tight">Remove this slot?</span>
                                <div className="flex gap-1">
                                  <button
                                    className="px-2 py-0.5 rounded text-[10px] font-bold border border-outline-variant text-on-surface-variant hover:bg-surface-container transition-colors"
                                    onClick={(e) => { e.stopPropagation(); onSlotDeleteCancel() }}
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    className="px-2 py-0.5 rounded text-[10px] font-bold bg-error text-on-error hover:bg-error/90 transition-colors"
                                    onClick={(e) => { e.stopPropagation(); onSlotDeleteConfirm(s.id) }}
                                  >
                                    Remove
                                  </button>
                                </div>
                              </div>
                            )}
                          </div>
                        )
                      })
                    }

                    {/* Pending slot overlay */}
                    {pendingOverlayStyle && (
                      <div
                        style={{ ...pendingOverlayStyle, pointerEvents: 'none' }}
                        className="border-2 border-dashed border-secondary bg-secondary/20 rounded-md z-10"
                      >
                        <div
                          style={{ pointerEvents: 'auto' }}
                          className="absolute top-0 left-0 right-0 h-2 cursor-ns-resize"
                          onMouseDown={(e) => { e.stopPropagation(); onPendingSlotEdgeMouseDown('top', e) }}
                        />
                        <div
                          style={{ pointerEvents: 'auto' }}
                          className="absolute bottom-0 left-0 right-0 h-2 cursor-ns-resize"
                          onMouseDown={(e) => { e.stopPropagation(); onPendingSlotEdgeMouseDown('bottom', e) }}
                        />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
