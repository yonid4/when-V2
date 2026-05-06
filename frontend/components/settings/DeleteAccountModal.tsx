'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Trash2, AlertTriangle } from 'lucide-react'
import { useDeleteAccount } from '@/hooks/useDeleteAccount'
import { useAuthStore } from '@/stores/authStore'

export function DeleteAccountModal({ onClose }: { onClose: () => void }) {
  const router = useRouter()
  const clearAuth = useAuthStore((s) => s.clearAuth)
  const { mutate: deleteAccount, isPending } = useDeleteAccount()
  const [error, setError] = useState<string | null>(null)

  function handleDelete() {
    setError(null)
    deleteAccount(undefined, {
      onSuccess: () => {
        clearAuth()
        router.push('/')
      },
      onError: (err: unknown) => {
        const message =
          err && typeof err === 'object' && 'detail' in err && typeof err.detail === 'string'
            ? err.detail
            : 'Could not delete your account. Please try again.'
        setError(message)
      },
    })
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-on-surface/40 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-surface-container-lowest rounded-2xl w-full max-w-md shadow-warm-md">
        <div className="p-8 text-center space-y-4">
          <div className="w-14 h-14 rounded-full bg-error-container flex items-center justify-center mx-auto">
            <AlertTriangle className="w-6 h-6 text-on-error-container" />
          </div>
          <div>
            <h2 className="text-xl font-bold text-on-surface">Delete your account</h2>
            <p className="text-sm text-on-surface-variant mt-2">
              All your events, calendar connections, busy slots, and personal data will be{' '}
              <span className="font-semibold text-on-surface">permanently deleted</span>.
              We will also revoke When.&apos;s access to your Google Calendar.
              This action cannot be undone.
            </p>
          </div>
          {error && (
            <p
              role="alert"
              className="text-sm text-on-error-container bg-error-container/40 rounded-lg px-3 py-2"
            >
              {error}
            </p>
          )}
          <div className="flex gap-3 pt-2">
            <button
              onClick={onClose}
              disabled={isPending}
              className="flex-1 py-3 rounded-xl border border-outline-variant text-on-surface-variant font-semibold hover:bg-surface-container transition-colors disabled:opacity-60"
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              disabled={isPending}
              className="flex-1 py-3 rounded-xl bg-error text-on-error font-bold flex items-center justify-center gap-2 disabled:opacity-60 hover:-translate-y-0.5 transition-all duration-300"
            >
              <Trash2 className="w-4 h-4" />
              {isPending ? 'Deleting…' : 'Delete account'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
