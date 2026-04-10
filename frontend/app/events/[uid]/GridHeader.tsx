'use client'

import { Pencil } from 'lucide-react'

export function GridHeader({
  isEditMode,
  eventStatus,
  onEdit,
}: {
  isEditMode: boolean
  eventStatus: string
  onEdit: () => void
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h2 className="text-3xl font-extrabold font-headline text-primary tracking-tight">
          Availability Grid
        </h2>
        {/* Legend */}
        <div className="flex flex-wrap gap-4 text-[10px] sm:text-xs font-bold uppercase tracking-wider">
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-error" />
            Busy
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-secondary" />
            Preferred
          </div>
          <div className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-primary-container/40" />
            Proposed
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full overflow-hidden flex border border-error/10">
              <div className="w-1/2 h-full bg-error" />
              <div className="w-1/2 h-full bg-secondary" />
            </div>
            Conflict
          </div>
        </div>
      </div>

      {/* Heatmap intensity legend */}
      <div className="flex items-center gap-3 bg-surface-container-low px-3 py-2 rounded-lg w-fit ml-auto">
        <span className="text-[10px] font-bold text-on-surface-variant/60 uppercase tracking-tighter">
          Intensity (Heatmap)
        </span>
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded-sm bg-error/20" />
          <div className="w-2.5 h-2.5 rounded-sm bg-error/40" />
          <div className="w-2.5 h-2.5 rounded-sm bg-error/70" />
          <div className="w-2.5 h-2.5 rounded-sm bg-error" />
        </div>
        <div className="flex items-center gap-1 ml-1">
          <div className="w-2.5 h-2.5 rounded-sm bg-secondary/20" />
          <div className="w-2.5 h-2.5 rounded-sm bg-secondary/40" />
          <div className="w-2.5 h-2.5 rounded-sm bg-secondary/70" />
          <div className="w-2.5 h-2.5 rounded-sm bg-secondary" />
        </div>
        <span className="text-[10px] font-bold text-on-surface-variant/40 ml-1">+ People</span>
      </div>

      {/* Edit availability button — sits above grid card when not in edit mode */}
      {!isEditMode && eventStatus !== 'confirmed' && (
        <div className="flex justify-end">
          <button
            data-testid="edit-availability-btn"
            onClick={onEdit}
            className="flex items-center gap-1.5 px-4 py-2 rounded-lg border border-outline-variant text-on-surface-variant text-xs font-bold hover:bg-surface-container transition-colors"
          >
            <Pencil className="w-3.5 h-3.5" />
            Edit Availability
          </button>
        </div>
      )}
    </div>
  )
}
