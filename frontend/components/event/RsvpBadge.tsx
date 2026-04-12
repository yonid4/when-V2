function RsvpBadge({ status, rsvpStatus }: { status: string; rsvpStatus: string | null }) {
  const display = rsvpStatus ?? status
  const styles: Record<string, string> = {
    going: 'bg-secondary-container text-on-secondary-container',
    accepted: 'bg-secondary-container text-on-secondary-container',
    maybe: 'bg-surface-container-high text-on-surface-variant',
    not_going: 'bg-error-container text-on-error-container',
    pending: 'bg-surface-container-high text-on-surface-variant',
    invited: 'bg-surface-container-high text-on-surface-variant',
    declined: 'bg-error-container text-on-error-container',
  }
  return (
    <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide ${styles[display] ?? styles.pending}`}>
      {display.replace('_', ' ')}
    </span>
  )
}

export default RsvpBadge
