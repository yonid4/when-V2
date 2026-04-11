export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    confirmed: 'bg-secondary-container text-on-secondary-container',
    planning: 'bg-surface-container-high text-on-surface-variant',
    cancelled: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`text-xs font-semibold capitalize px-2 py-0.5 rounded-full ${styles[status] ?? styles.planning}`}>
      {status}
    </span>
  )
}
