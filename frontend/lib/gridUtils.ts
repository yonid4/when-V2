import type { SlotOverlay, ConflictOverlay } from '@/types'

export interface SlotLike {
  start_time_utc: string
  end_time_utc: string
  user_id: string
}

/**
 * Returns all slots that overlap the half-hour cell defined by
 * [cellStartUtc, cellEndUtc).
 *
 * Overlap rule (strict inequality on both ends):
 *   slot.start < cellEnd  AND  slot.end > cellStart
 *
 * A slot ending exactly when the cell starts is NOT an overlap.
 * A slot starting exactly when the cell ends is NOT an overlap.
 */
export function getSlotsForCell(
  cellStartUtc: Date,
  cellEndUtc: Date,
  slots: SlotLike[]
): SlotLike[] {
  return slots.filter((slot) => {
    const slotStart = new Date(slot.start_time_utc)
    const slotEnd = new Date(slot.end_time_utc)
    return slotStart < cellEndUtc && slotEnd > cellStartUtc
  })
}

export function busyIntensityClass(count: number): string {
  if (count >= 7) return 'bg-error/90'
  if (count >= 5) return 'bg-error/65'
  if (count >= 3) return 'bg-error/40'
  return 'bg-error/20'
}

export function preferredIntensityClass(count: number): string {
  if (count >= 7) return 'bg-secondary/90'
  if (count >= 5) return 'bg-secondary/65'
  if (count >= 3) return 'bg-secondary/40'
  return 'bg-secondary/20'
}

/** Group continuous/overlapping slots of the same type into merged overlay blocks. */
export function mergeSlots(slots: SlotLike[]): SlotOverlay[] {
  if (slots.length === 0) return []
  const sorted = [...slots].sort(
    (a, b) => new Date(a.start_time_utc).getTime() - new Date(b.start_time_utc).getTime(),
  )
  const result: SlotOverlay[] = []
  let curStart = new Date(sorted[0].start_time_utc)
  let curEnd = new Date(sorted[0].end_time_utc)
  let curCount = 1

  for (let i = 1; i < sorted.length; i++) {
    const s = new Date(sorted[i].start_time_utc)
    const e = new Date(sorted[i].end_time_utc)
    if (s <= curEnd) {
      if (e > curEnd) curEnd = e
      curCount++
    } else {
      result.push({ startUtc: curStart, endUtc: curEnd, count: curCount })
      curStart = s
      curEnd = e
      curCount = 1
    }
  }
  result.push({ startUtc: curStart, endUtc: curEnd, count: curCount })
  return result
}

/** Build conflict overlays: only the intersection where busy and preferred overlap. */
export function buildConflictOverlays(
  busyOverlays: SlotOverlay[],
  preferredOverlays: SlotOverlay[],
): ConflictOverlay[] {
  const conflicts: ConflictOverlay[] = []
  for (const b of busyOverlays) {
    for (const p of preferredOverlays) {
      const overlapStart = b.startUtc > p.startUtc ? b.startUtc : p.startUtc
      const overlapEnd = b.endUtc < p.endUtc ? b.endUtc : p.endUtc
      if (overlapStart < overlapEnd) {
        conflicts.push({ startUtc: overlapStart, endUtc: overlapEnd, busyCount: b.count, preferredCount: p.count })
      }
    }
  }
  return conflicts
}

/** Return the portions of overlay NOT covered by any conflict. */
export function subtractConflicts(
  overlay: SlotOverlay,
  conflicts: ConflictOverlay[],
): Array<{ startUtc: Date; endUtc: Date }> {
  let segments: Array<{ startUtc: Date; endUtc: Date }> = [
    { startUtc: overlay.startUtc, endUtc: overlay.endUtc },
  ]
  for (const conflict of conflicts) {
    const next: Array<{ startUtc: Date; endUtc: Date }> = []
    for (const seg of segments) {
      if (seg.startUtc < conflict.startUtc) {
        next.push({ startUtc: seg.startUtc, endUtc: conflict.startUtc < seg.endUtc ? conflict.startUtc : seg.endUtc })
      }
      if (seg.endUtc > conflict.endUtc) {
        next.push({ startUtc: conflict.endUtc > seg.startUtc ? conflict.endUtc : seg.startUtc, endUtc: seg.endUtc })
      }
    }
    segments = next
  }
  return segments.filter((s) => s.endUtc > s.startUtc)
}

/**
 * Break a list of slots into non-overlapping segments with accurate per-segment
 * participant counts. Each boundary point (slot start/end) becomes a segment
 * boundary, and each segment's count = number of input slots that cover it.
 */
export function buildCountedSegments(slots: SlotLike[]): SlotOverlay[] {
  if (slots.length === 0) return []
  const points = Array.from(
    new Set(slots.flatMap((s) => [new Date(s.start_time_utc).getTime(), new Date(s.end_time_utc).getTime()]))
  ).sort((a, b) => a - b)

  const raw: SlotOverlay[] = []
  for (let i = 0; i < points.length - 1; i++) {
    const segStart = new Date(points[i])
    const segEnd = new Date(points[i + 1])
    const count = slots.filter((s) => {
      const ss = new Date(s.start_time_utc).getTime()
      const se = new Date(s.end_time_utc).getTime()
      return ss <= points[i] && se >= points[i + 1]
    }).length
    if (count > 0) raw.push({ startUtc: segStart, endUtc: segEnd, count })
  }

  if (raw.length === 0) return []
  const result: SlotOverlay[] = [{ ...raw[0] }]
  for (let i = 1; i < raw.length; i++) {
    const last = result[result.length - 1]
    if (preferredIntensityClass(raw[i].count) === preferredIntensityClass(last.count) && raw[i].startUtc.getTime() === last.endUtc.getTime()) {
      last.endUtc = raw[i].endUtc
      if (raw[i].count > last.count) last.count = raw[i].count
    } else {
      result.push({ ...raw[i] })
    }
  }
  return result
}

/** Clip a slot's start/end to the grid's visible time bounds for a given column. */
export function clipToGridBounds(
  startUtc: Date,
  endUtc: Date,
  gridStartUtc: Date,
  gridEndUtc: Date,
): { startUtc: Date; endUtc: Date } {
  return {
    startUtc: startUtc < gridStartUtc ? gridStartUtc : startUtc,
    endUtc: endUtc > gridEndUtc ? gridEndUtc : endUtc,
  }
}
