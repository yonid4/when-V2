import type { PreferredSlot, PendingSlot, MergeResult } from '@/types'

/**
 * Computes the merge of a pending slot against confirmed preferred slots.
 *
 * For each confirmed slot on the same day that overlaps the pending slot:
 *   - Expand pendingSlot to cover both ranges
 *   - Add the confirmed slot's id to slotsToDelete
 *   - Remove it from remainingSlots
 *
 * Non-overlapping slots and slots on different days are unaffected.
 *
 * @param pending - The pending slot being drawn
 * @param confirmedSlots - All current confirmed preferred slots
 * @param getDayIndex - Function to compute a day-column index from a slot's start time
 */
export function computeMerge(
  pending: PendingSlot,
  confirmedSlots: PreferredSlot[],
  getDayIndex: (slot: PreferredSlot) => number
): MergeResult {
  let startUtc = pending.startUtc
  let endUtc = pending.endUtc
  const slotsToDelete: string[] = []
  const remainingSlots: PreferredSlot[] = []

  for (const slot of confirmedSlots) {
    const slotDayIndex = getDayIndex(slot)
    if (slotDayIndex !== pending.dayIndex) {
      remainingSlots.push(slot)
      continue
    }

    const slotStart = new Date(slot.start_time_utc)
    const slotEnd = new Date(slot.end_time_utc)
    const overlaps = startUtc <= slotEnd && endUtc >= slotStart

    if (overlaps) {
      // Expand the pending slot to cover both ranges
      if (slotStart < startUtc) startUtc = slotStart
      if (slotEnd > endUtc) endUtc = slotEnd
      slotsToDelete.push(slot.id)
    } else {
      remainingSlots.push(slot)
    }
  }

  return {
    pendingSlot: { ...pending, startUtc, endUtc },
    slotsToDelete,
    remainingSlots,
  }
}
