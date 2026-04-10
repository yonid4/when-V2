'use client'

import { Check } from 'lucide-react'

export function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  const steps = ['Details', 'Availability', 'Confirm']
  return (
    <div className="flex items-center justify-between mb-12 relative px-4">
      <div className="absolute top-5 left-8 right-8 h-0.5 bg-surface-container-high -z-10" />
      {steps.map((label, i) => {
        const n = i + 1
        const done = n < current
        const active = n === current
        return (
          <div key={label} className="flex flex-col items-center gap-2 bg-surface px-2">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm transition-all duration-300
                ${done ? 'bg-secondary-container text-on-secondary-container' : ''}
                ${active ? 'bg-gradient-to-br from-primary to-primary-container text-on-primary shadow-warm' : ''}
                ${!done && !active ? 'bg-surface-container-high text-on-surface-variant' : ''}
              `}
            >
              {done ? <Check className="w-4 h-4" /> : n}
            </div>
            <span
              className={`text-xs font-bold uppercase tracking-wider ${
                active ? 'text-primary' : done ? 'text-on-secondary-container' : 'text-on-surface-variant'
              }`}
            >
              {label}
            </span>
          </div>
        )
      })}
    </div>
  )
}
