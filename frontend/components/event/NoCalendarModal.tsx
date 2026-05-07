'use client'

import { Settings } from 'lucide-react'

interface NoCalendarModalProps {
  onClose: () => void
}

export function NoCalendarModal({ onClose }: NoCalendarModalProps) {
  return (
    <div className="fixed inset-0 z-60 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-sm shadow-warm-md p-6 flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-full bg-error-container flex items-center justify-center">
          <Settings className="w-6 h-6 text-on-error-container" />
        </div>
        <div className="text-center space-y-1">
          <h3 className="text-base font-bold text-on-surface">No Calendar Connected</h3>
          <p className="text-sm text-on-surface-variant">
            You need to connect a Google Calendar in Settings before you can finalize an event.
          </p>
        </div>
        <div className="flex flex-col gap-2 w-full">
          <a
            href="/settings"
            className="w-full py-3 rounded-xl bg-primary text-on-primary font-bold text-sm text-center hover:opacity-90 transition-opacity"
          >
            Go to Settings
          </a>
          <button
            onClick={onClose}
            className="w-full py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold text-sm hover:bg-surface-container transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
