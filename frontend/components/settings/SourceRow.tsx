'use client'

import { useState } from 'react'
import type { CalendarSource } from '@/types'

interface SourceRowProps {
  source: CalendarSource
  onToggle: (enabled: boolean) => void
  onSetWrite: () => void
}

export function SourceRow({ source, onToggle, onSetWrite }: SourceRowProps) {
  const [showReadOnlyNotice, setShowReadOnlyNotice] = useState(false)

  function handleWriteChange() {
    if (source.is_writable) {
      onSetWrite()
    } else {
      // Can't create events on a read-only calendar — explain instead of switching.
      setShowReadOnlyNotice(true)
    }
  }

  return (
    <div className="bg-surface-container-lowest rounded-xl transition-all duration-300 hover:-translate-y-0.5">
      <div className="flex items-center justify-between p-4">
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
            title={
              source.is_writable
                ? 'Events will be added to this calendar when you finalize a meeting'
                : "This calendar is read-only — events can't be created on it"
            }
          >
            <input
              type="radio"
              name="write-calendar"
              checked={source.is_write_calendar}
              onChange={handleWriteChange}
              className="accent-primary w-4 h-4 cursor-pointer"
            />
            <span
              className={`text-xs font-semibold transition-colors ${
                source.is_writable
                  ? 'text-on-surface-variant group-hover:text-primary'
                  : 'text-on-surface-variant/60'
              }`}
            >
              Write calendar{!source.is_writable && ' (read-only)'}
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
      {showReadOnlyNotice && !source.is_writable && (
        <p className="px-4 pb-3 -mt-1 text-xs text-error">
          &ldquo;{source.calendar_name}&rdquo; is read-only, so events can&apos;t be created on it —
          it can&apos;t be your write calendar. Choose a calendar you own, such as your primary
          calendar.
        </p>
      )}
    </div>
  )
}
