import type { CalendarSource } from '@/types'

interface SourceRowProps {
  source: CalendarSource
  onToggle: (enabled: boolean) => void
  onSetWrite: () => void
}

export function SourceRow({ source, onToggle, onSetWrite }: SourceRowProps) {
  return (
    <div className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl transition-all duration-300 hover:-translate-y-0.5">
      <div className="flex items-center gap-3">
        <div
          className="w-3 h-3 rounded-full shadow-sm"
          style={{ backgroundColor: source.color ?? 'var(--color-primary)' }}
        />
        <span className="font-medium">{source.calendar_name}</span>
      </div>
      <div className="flex items-center gap-4">
        <label
          className="flex items-center gap-2 cursor-pointer group"
          title="Events will be added to this calendar when you finalize a meeting"
        >
          <input
            type="radio"
            name="write-calendar"
            checked={source.is_write_calendar}
            onChange={onSetWrite}
            className="accent-primary w-4 h-4 cursor-pointer"
          />
          <span className="text-xs font-semibold text-on-surface-variant group-hover:text-primary transition-colors">
            Write calendar
          </span>
        </label>
        <label
          className={`relative inline-flex items-center ${source.is_write_calendar ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'}`}
          title={source.is_write_calendar ? 'This is your write calendar. Select another write calendar before disabling.' : undefined}
        >
          <input
            type="checkbox"
            className="sr-only peer"
            checked={source.is_enabled}
            onChange={(e) => onToggle(e.target.checked)}
            disabled={source.is_write_calendar}
          />
          <div className="w-11 h-6 bg-surface-container-high rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
        </label>
      </div>
    </div>
  )
}
