'use client'

import Image from 'next/image'
import { Pencil } from 'lucide-react'

interface PresenceUser {
  user_id: string
  avatar_url: string | null
  full_name: string | null
}

export function GridHeader({
  isEditMode,
  eventStatus,
  onEdit,
  presentUsers = [],
}: {
  isEditMode: boolean
  eventStatus: string
  onEdit: () => void
  presentUsers?: PresenceUser[]
}) {
  const visibleUsers = presentUsers.slice(0, 5)
  const overflowCount = presentUsers.length - visibleUsers.length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h2 className="text-3xl font-extrabold font-headline text-primary tracking-tight">
            Availability Grid
          </h2>
          {presentUsers.length > 0 && (
            <div className="flex items-center gap-1" title="Currently viewing">
              <div className="flex -space-x-1.5">
                {visibleUsers.map((u) =>
                  u.avatar_url ? (
                    <Image
                      key={u.user_id}
                      src={u.avatar_url}
                      alt={u.full_name ?? ''}
                      width={24}
                      height={24}
                      className="w-6 h-6 rounded-full border-2 border-surface object-cover"
                    />
                  ) : (
                    <div
                      key={u.user_id}
                      className="w-6 h-6 rounded-full border-2 border-surface bg-primary/20 flex items-center justify-center text-[9px] font-bold text-primary"
                    >
                      {(u.full_name ?? '?').charAt(0).toUpperCase()}
                    </div>
                  )
                )}
                {overflowCount > 0 && (
                  <div className="w-6 h-6 rounded-full border-2 border-surface bg-surface-container-high flex items-center justify-center text-[9px] font-bold text-on-surface-variant">
                    +{overflowCount}
                  </div>
                )}
              </div>
              <span className="text-[10px] text-on-surface-variant/60 ml-1">also viewing</span>
            </div>
          )}
        </div>
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
