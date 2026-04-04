'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Settings, LogOut } from 'lucide-react'
import { NotificationBell } from '@/components/notifications/NotificationBell'
import { useAuthStore } from '@/stores/authStore'
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from '@/components/ui/dropdown-menu'

export function Navbar() {
  const router = useRouter()
  const user = useAuthStore((s) => s.user)
  const clearAuth = useAuthStore((s) => s.clearAuth)

  const avatarLetter = user
    ? (user.full_name?.trim() || user.email_address).charAt(0).toUpperCase()
    : ''

  const avatarElement = user ? (
    user.avatar_url ? (
      <img
        src={user.avatar_url}
        alt={user.full_name ?? ''}
        className="w-9 h-9 rounded-full object-cover ring-2 ring-primary/20 hover:ring-primary/60 transition"
      />
    ) : (
      <div className="w-9 h-9 rounded-full bg-primary text-on-primary flex items-center justify-center text-sm font-bold ring-2 ring-primary/20 hover:ring-primary/60 transition select-none cursor-pointer">
        {avatarLetter}
      </div>
    )
  ) : null

  return (
    <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md border-b-0">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link href="/dashboard" className="text-2xl font-black text-primary tracking-tighter">
          When.
        </Link>
        <div className="flex items-center gap-3">
          <NotificationBell />
          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger className="rounded-full focus:outline-none">
                {avatarElement}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-44">
                <DropdownMenuItem
                  className="text-on-surface hover:bg-surface-container cursor-pointer"
                  onClick={() => router.push('/settings')}
                >
                  <Settings className="mr-2 h-4 w-4" />
                  Settings
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem
                  className="text-on-surface hover:bg-surface-container cursor-pointer"
                  onClick={() => {
                    clearAuth()
                    router.push('/')
                  }}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </div>
    </header>
  )
}
