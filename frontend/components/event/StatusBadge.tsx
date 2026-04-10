'use client'

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: 'bg-secondary-container text-on-secondary-container',
    planning: 'bg-surface-container-high text-on-surface-variant',
    cancelled: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-full ${styles[status] ?? styles.planning}`}>
      {status}
    </span>
  )
}
