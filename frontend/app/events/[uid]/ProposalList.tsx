'use client'

import { RefreshCw, Calendar, CalendarCheck } from 'lucide-react'
import type { ProposalResponse } from '@/types'
import { formatDayLabel, formatTime } from '@/lib/dates'

export function ProposalList({
  proposals,
  isLoadingProposals,
  isCoordinator,
  isRefreshing,
  proposalsStale,
  proposalsNeedsRegeneration,
  onRefresh,
  onFinalize,
}: {
  proposals: ProposalResponse[]
  isLoadingProposals: boolean
  isCoordinator: boolean
  isRefreshing: boolean
  proposalsStale: boolean
  proposalsNeedsRegeneration: boolean
  onRefresh: () => void
  onFinalize: () => void
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between px-1">
        <label className="text-[10px] font-extrabold text-outline uppercase tracking-[0.2em]">
          Top Proposals
        </label>
        {isCoordinator && (
          <button
            onClick={onRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-1 text-[10px] font-bold text-primary uppercase tracking-wider hover:text-primary/70 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
            {isRefreshing ? 'Regenerating…' : 'Regenerate'}
          </button>
        )}
      </div>

      {isCoordinator && (
        <button
          onClick={onFinalize}
          className="w-full py-2.5 rounded-xl bg-primary text-on-primary text-sm font-bold flex items-center justify-center gap-2 hover:-translate-y-0.5 transition-all duration-300"
        >
          <CalendarCheck className="w-4 h-4" />
          Finalize Event
        </button>
      )}

      {/* Stale banner */}
      {(proposalsStale || proposalsNeedsRegeneration) && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-tertiary-container/40 border border-tertiary/20">
          <RefreshCw className="w-3.5 h-3.5 text-on-tertiary-container flex-shrink-0" />
          <p className="text-xs font-medium text-on-tertiary-container">
            Availability changed — proposals may be outdated.
          </p>
        </div>
      )}

      {isLoadingProposals && (
        <div className="flex items-center justify-center py-8">
          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
        </div>
      )}

      {!isLoadingProposals && proposals.length === 0 && (
        <div className="bg-surface-container-lowest p-4 rounded-xl flex items-center gap-4 shadow-sm">
          <div className="h-10 w-10 bg-surface-container-low rounded-lg flex items-center justify-center text-primary flex-shrink-0">
            <Calendar className="w-5 h-5" />
          </div>
          <p className="text-sm font-medium text-on-surface-variant">
            No proposals yet — add availability to generate proposals.
          </p>
        </div>
      )}

      {!isLoadingProposals && proposals.length > 0 && (
        <div className="space-y-3">
          {proposals.map((proposal) => {
            const dayLabel = formatDayLabel(proposal.start_time_utc)
            const timeRange = `${formatTime(proposal.start_time_utc)} – ${formatTime(proposal.end_time_utc)}`
            return (
              <div
                key={proposal.id}
                className="bg-surface-container-lowest rounded-xl p-4 shadow-sm border border-outline-variant/20 space-y-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-bold text-on-surface">{dayLabel}</p>
                    <p className="text-xs font-medium text-on-surface-variant">{timeRange}</p>
                  </div>
                  <span className="text-[10px] font-bold text-primary bg-primary/10 px-2 py-0.5 rounded-full shrink-0">
                    #{proposal.rank}
                  </span>
                </div>
                <p className="text-xs text-on-surface-variant">{proposal.reasoning}</p>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
