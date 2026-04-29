'use client'

import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Settings, LogOut, AlertTriangle } from 'lucide-react'
import { NotificationBell } from '@/components/notifications/NotificationBell'
import { useAuthStore } from '@/stores/authStore'
import { useCalendarAccounts } from '@/hooks/useCalendarAccounts'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
} from '@/components/ui/dropdown-menu'

export function Navbar() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { data: accounts = [] } = useCalendarAccounts()
  const staleAccounts = accounts.filter((a) => a.needs_reauth)
  const showReauthPill = user && staleAccounts.length > 0
  const reauthLabel = staleAccounts.length > 1 ? 'Reconnect Calendars' : 'Reconnect Calendar'

  function handleReauthClick() {
    router.push('/settings')
  }

  const avatarLetter = user
    ? (user.full_name?.trim() || user.email_address).charAt(0).toUpperCase()
    : ''

  const avatarElement = user ? (
    user.avatar_url ? (
      <Image
        src={user.avatar_url}
        alt={user.full_name ?? ''}
        width={36}
        height={36}
        className="w-9 h-9 rounded-full object-cover ring-2 ring-primary/20 hover:ring-primary/60 transition"
      />
    ) : (
      <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center text-sm font-bold ring-2 ring-primary/20 hover:ring-primary/60 transition select-none cursor-pointer">
        {avatarLetter}
      </div>
    )
  ) : null

  return (
    <header className="w-full sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b-0">
      <div className="w-full flex items-center justify-between px-4 h-16">
        <Link href="/dashboard">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/navbar_logo.png" alt="When." className="h-13 w-auto object-contain" />
        </Link>
        <div className="flex items-center gap-3">
          {showReauthPill && (
            <button
              type="button"
              onClick={handleReauthClick}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-error-container text-on-error-container text-xs font-semibold hover:opacity-90 transition-opacity cursor-pointer"
              title={
                staleAccounts.length > 1
                  ? 'Multiple calendars need reconnection — open Settings'
                  : `Reconnect ${staleAccounts[0]?.provider_email ?? 'calendar'}`
              }
            >
              <AlertTriangle className="w-3.5 h-3.5" />
              {reauthLabel}
            </button>
          )}
          <NotificationBell />
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full focus:outline-none">
                {avatarElement}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="min-w-44 p-1">
                <div
                  className="flex items-center gap-2 px-3 py-2 rounded-sm text-sm cursor-pointer hover:bg-gray-100 w-full"
                  onClick={() => router.push('/settings')}
                >
                  <Settings className="h-4 w-4" />
                  Settings
                </div>
                <div className="h-px bg-gray-200 my-1" />
                <div
                  className="flex items-center gap-2 px-3 py-2 rounded-sm text-sm cursor-pointer hover:bg-gray-100 w-full"
                  onClick={() => {
                    clearAuth()
                    router.push('/')
                  }}
                >
                  <LogOut className="h-4 w-4" />
                  Log out
                </div>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
