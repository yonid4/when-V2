import type { EventType } from '@/types'

export function typeLabel(t: EventType): string {
  return t.charAt(0).toUpperCase() + t.slice(1).replace('_', ' ')
}

/**
 * Returns true only for http/https URLs. A video-call link is rendered into an
 * anchor `href`, so a `javascript:` (or other) scheme would be an XSS sink.
 * Uses a real URL parse rather than a substring check because `javascript:` can
 * be disguised with leading whitespace/control chars that a `startsWith` misses.
 */
export function isSafeHttpUrl(value: string | null | undefined): boolean {
  if (!value) return false
  try {
    const { protocol } = new URL(value)
    return protocol === 'http:' || protocol === 'https:'
  } catch {
    return false
  }
}
