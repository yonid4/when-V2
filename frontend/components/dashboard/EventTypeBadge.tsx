const EVENT_TYPE_STYLES: Record<string, string> = {
  meeting: 'bg-blue-100 text-blue-700',
  social: 'bg-purple-100 text-purple-700',
  birthday: 'bg-pink-100 text-pink-700',
  other: 'bg-gray-100 text-gray-600',
}

export function EventTypeBadge({ type }: { type: string }) {
  const typeStyle = EVENT_TYPE_STYLES[type?.toLowerCase()] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full ${typeStyle}`}>
      {type}
    </span>
  )
}
