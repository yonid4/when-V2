'use client'

import Link from 'next/link'
import { Calendar, Plus, Trash2, RefreshCw } from 'lucide-react'
import { NotificationBell } from '@/components/notifications/NotificationBell'
import { useCalendarAccounts, useDisconnectCalendarAccount, useUpdateCalendarSource } from '@/hooks/useCalendarAccounts'
import { useSyncMyCalendar } from '@/hooks/useBusySlots'
import type { CalendarSource } from '@/types'

export default function SettingsPage() {
  const { data: accounts = [], isLoading } = useCalendarAccounts()
  const disconnect = useDisconnectCalendarAccount()
  const updateSource = useUpdateCalendarSource()
  const sync = useSyncMyCalendar()

  return (
    <>
      {/* Top Nav */}
      <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link href="/dashboard" className="text-2xl font-black text-primary tracking-tighter">When.</Link>
          <nav className="hidden md:flex items-center gap-8">
            <Link href="/dashboard" className="text-on-surface-variant hover:text-primary transition-colors text-sm">Events</Link>
            <Link href="/settings" className="text-primary font-bold text-sm">Settings</Link>
          </nav>
          <div className="flex items-center gap-3">
            <NotificationBell />
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-12">
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
                      </div>
                    </div>
                    <button
                      onClick={() => disconnect.mutate(account.id)}
                      disabled={disconnect.isPending}
                      className="px-5 py-2 text-sm font-semibold text-error bg-error-container/30 hover:bg-error-container/50 rounded-full transition-colors duration-300 disabled:opacity-60 flex items-center gap-2"
                    >
                      <Trash2 className="w-4 h-4" />
                      Disconnect
                    </button>
                  </div>

                  {/* Calendar sources */}
                  {account.sources.length > 0 && (
                    <div className="space-y-3">
                      <p className="text-xs font-bold uppercase tracking-widest text-on-surface-variant px-2">
                        Calendar Sources
                      </p>
                      <div className="space-y-1">
                        {account.sources.map((source: CalendarSource) => (
                          <SourceRow
                            key={source.id}
                            source={source}
                            onToggle={(enabled) =>
                              updateSource.mutate({ sourceId: source.id, data: { is_enabled: enabled } })
                            }
                          />
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {/* Connect another account */}
              <a
                href="/api/calendar-accounts/connect"
                className="w-full py-4 border-2 border-dashed border-outline-variant/40 rounded-xl text-primary font-bold hover:bg-white hover:border-primary/40 transition-all duration-300 active:scale-95 flex items-center justify-center gap-2"
              >
                <Plus className="w-5 h-5" />
                Connect another account
              </a>
            </div>
          </section>

          {/* Footer */}
          <footer className="mt-4 pt-8 border-t border-outline-variant/10 flex justify-between items-center flex-wrap gap-4">
            <p className="text-sm text-on-surface-variant">
              {accounts[0]?.last_synced_at
                ? `Last synced ${new Date(accounts[0].last_synced_at).toLocaleString()}`
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

function SourceRow({
  source,
  onToggle,
}: {
  source: CalendarSource
  onToggle: (enabled: boolean) => void
}) {
  return (
    <div className="flex items-center justify-between p-4 bg-surface-container-lowest rounded-xl transition-all duration-300 hover:-translate-y-0.5">
      <div className="flex items-center gap-3">
        <div
          className="w-3 h-3 rounded-full shadow-sm"
          style={{ backgroundColor: source.color ?? 'var(--color-primary)' }}
        />
        <span className="font-medium">{source.calendar_name}</span>
        {source.is_write_calendar && (
          <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 bg-primary-container/30 text-on-primary-container rounded-full">
            Write
          </span>
        )}
      </div>
      <label className="relative inline-flex items-center cursor-pointer">
        <input
          type="checkbox"
          className="sr-only peer"
          checked={source.is_enabled}
          onChange={(e) => onToggle(e.target.checked)}
        />
        <div className="w-11 h-6 bg-surface-container-high rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary" />
      </label>
    </div>
  )
}
