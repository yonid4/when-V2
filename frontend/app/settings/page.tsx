'use client'

export const dynamic = 'force-dynamic'

import { useSearchParams } from 'next/navigation'
import { Calendar, Plus, Trash2, RefreshCw, X, AlertTriangle, RotateCw } from 'lucide-react'
import { useState } from 'react'
import { useCalendarAccounts, useDisconnectCalendarAccount, useUpdateCalendarSource, useConnectCalendarAccount } from '@/hooks/useCalendarAccounts'
import { formatDateTime } from '@/lib/dates'
import { Navbar } from '@/components/layout/Navbar'
import { useSyncMyCalendar } from '@/hooks/useBusySlots'
import { SourceRow } from '@/components/settings/SourceRow'

export default function SettingsPage() {
  const { data: accounts = [], isLoading } = useCalendarAccounts()
  const disconnect = useDisconnectCalendarAccount()
  const updateSource = useUpdateCalendarSource()
  const sync = useSyncMyCalendar()
  const connectCalendar = useConnectCalendarAccount()
  const searchParams = useSearchParams()
  const [bannerDismissed, setBannerDismissed] = useState(false)
  const showCalendarBanner = searchParams.get('connect_calendar') === 'true' && !bannerDismissed

  async function handleConnectCalendar() {
    await connectCalendar()
  }

  return (
    <>
      <Navbar />

      <main className="max-w-4xl mx-auto px-6 py-12">
        {showCalendarBanner && (
          <div className="mb-8 flex items-center justify-between gap-4 px-5 py-4 rounded-xl bg-primary-fixed text-on-surface">
            <p className="text-sm font-semibold">You need to connect a calendar before joining events.</p>
            <button onClick={() => setBannerDismissed(true)} className="shrink-0 p-1 rounded-full hover:bg-surface-container/40 transition-colors">
              <X className="w-4 h-4" />
            </button>
          </div>
        )}

        <header className="mb-12">
          <h1 className="text-4xl font-extrabold text-on-surface tracking-tight mb-2">Settings</h1>
          <p className="text-on-surface-variant tracking-wide">Manage your integrations and calendar preferences.</p>
        </header>

        <div className="flex flex-col gap-10">
          {/* Calendar Accounts */}
          <section className="space-y-6">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-primary" />
              <h2 className="text-xl font-bold text-on-surface">Calendar Accounts</h2>
            </div>

            <div className="bg-surface-container-low rounded-xl p-8 space-y-8">
              {isLoading && (
                <p className="text-sm text-on-surface-variant">Loading accounts…</p>
              )}

              {!isLoading && accounts.length === 0 && (
                <p className="text-sm text-on-surface-variant">No calendars connected yet.</p>
              )}

              {accounts.map((account) => (
                <div key={account.id} className="space-y-6">
                  {/* Account header */}
                  <div className="flex items-center justify-between flex-wrap gap-4">
                    <div className="flex items-center gap-4">
                      <div className="w-12 h-12 rounded-lg bg-surface-container-lowest flex items-center justify-center">
                        <Calendar className="w-6 h-6 text-primary" />
                      </div>
                      <div>
                        <h3 className="font-bold text-lg capitalize">{account.provider} Calendar</h3>
                        <p className="text-sm text-on-surface-variant">{account.provider_email}</p>
                        {account.needs_reauth && (
                          <p className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-error">
                            <AlertTriangle className="w-3.5 h-3.5" />
                            Reconnection required
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {account.needs_reauth && (
                        <button
                          onClick={handleConnectCalendar}
                          className="px-5 py-2 text-sm font-semibold text-on-primary bg-primary hover:opacity-90 rounded-full transition-opacity duration-300 flex items-center gap-2"
                        >
                          <RotateCw className="w-4 h-4" />
                          Reconnect
                        </button>
                      )}
                      <button
                        onClick={() => disconnect.mutate(account.id)}
                        disabled={disconnect.isPending}
                        className="px-5 py-2 text-sm font-semibold text-error bg-error-container/30 hover:bg-error-container/50 rounded-full transition-colors duration-300 disabled:opacity-60 flex items-center gap-2"
                      >
                        <Trash2 className="w-4 h-4" />
                        Disconnect
                      </button>
                    </div>
                  </div>

                  {/* Calendar sources */}
                  {account.sources.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant px-2">
                        Calendar Sources
                      </p>
                      <div className="space-y-1">
                        {[...account.sources].sort((a, b) => a.calendar_name.localeCompare(b.calendar_name)).map((source) => (
                          <SourceRow
                            key={source.id}
                            source={source}
                            onToggle={(enabled) =>
                              updateSource.mutate({ sourceId: source.id, data: { is_enabled: enabled } })
                            }
                            onSetWrite={() =>
                              updateSource.mutate({ sourceId: source.id, data: { is_write_calendar: true } })
                            }
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Connect another account */}
              <button
                onClick={handleConnectCalendar}
                className="w-full py-4 border-2 border-dashed border-outline-variant/40 rounded-xl text-primary font-bold hover:bg-white hover:border-primary/40 transition-all duration-300 active:scale-95 flex items-center justify-center gap-2"
              >
                <Plus className="w-5 h-5" />
                Connect another account
              </button>
            </div>
          </section>

          {/* Footer */}
          <footer className="mt-4 pt-8 border-t border-outline-variant/10 flex justify-between items-center flex-wrap gap-4">
            <p className="text-sm text-on-surface-variant">
              {accounts[0]?.last_synced_at
                ? `Last synced ${formatDateTime(accounts[0].last_synced_at)}`
                : 'Not yet synced'}
            </p>
            <button
              onClick={() => sync.mutate()}
              disabled={sync.isPending}
              className="bg-gradient-to-br from-primary to-primary-container text-on-primary px-8 py-3 rounded-full font-bold shadow-[0_20px_40px_-15px_rgba(155,68,40,0.2)] hover:-translate-y-0.5 transition-all duration-500 active:scale-90 disabled:opacity-60 flex items-center gap-2"
            >
              <RefreshCw className={`w-4 h-4 ${sync.isPending ? 'animate-spin' : ''}`} />
              {sync.isPending ? 'Syncing…' : 'Sync Now'}
            </button>
          </footer>
        </div>
      </main>
    </>
  )
}
