import type { EventType } from '@/types'

export function typeLabel(t: EventType): string {
  return t.charAt(0).toUpperCase() + t.slice(1).replace('_', ' ')
}
