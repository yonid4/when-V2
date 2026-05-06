import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── Mocks ────────────────────────────────────────────────────────────────────

const mockDeleteAccount = vi.fn()
let mockIsPending = false
const mockClearAuth = vi.fn()
const mockRouterPush = vi.fn()

vi.mock('@/hooks/useDeleteAccount', () => ({
  useDeleteAccount: () => ({
    mutate: (_v: unknown, opts?: { onSuccess?: () => void; onError?: (e: unknown) => void }) => {
      mockDeleteAccount(opts)
    },
    isPending: mockIsPending,
  }),
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: (s: { clearAuth: () => void }) => unknown) =>
    selector({ clearAuth: mockClearAuth }),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockRouterPush }),
  usePathname: () => '/settings',
  useSearchParams: () => ({ get: vi.fn().mockReturnValue(null) }),
}))

// Mocks for the rest of SettingsPage's dependencies (we're not testing them here)
const mockDisconnect = vi.fn()
const mockUpdateSource = vi.fn()
const mockSync = vi.fn()
vi.mock('@/hooks/useCalendarAccounts', () => ({
  useCalendarAccounts: () => ({ data: [], isLoading: false }),
  useDisconnectCalendarAccount: () => ({ mutate: mockDisconnect, isPending: false }),
  useUpdateCalendarSource: () => ({ mutate: mockUpdateSource, isPending: false }),
  useConnectCalendarAccount: () => vi.fn(),
}))
vi.mock('@/hooks/useBusySlots', () => ({
  useSyncMyCalendar: () => ({ mutate: mockSync, isPending: false }),
}))
vi.mock('@/components/notifications/NotificationBell', () => ({
  NotificationBell: () => <div>Bell</div>,
}))

import SettingsPage from '@/app/settings/page'
import { DeleteAccountModal } from '@/components/settings/DeleteAccountModal'

// ─── Tests ────────────────────────────────────────────────────────────────────

describe('Settings page — Delete account button', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsPending = false
  })

  it('renders the Delete Account section', () => {
    render(<SettingsPage />)
    expect(screen.getByText('Danger Zone')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /delete my account/i })).toBeInTheDocument()
  })

  it('clicking the button opens the confirmation modal', () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('button', { name: /delete my account/i }))
    // Modal title is an h2; the Danger Zone section uses h3 for the same text
    expect(screen.getByRole('heading', { level: 2, name: /delete your account/i })).toBeInTheDocument()
    expect(screen.getByText(/permanently deleted/i)).toBeInTheDocument()
  })

  it('canceling the modal does not call the API', () => {
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('button', { name: /delete my account/i }))
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(mockDeleteAccount).not.toHaveBeenCalled()
  })
})


describe('DeleteAccountModal', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockIsPending = false
  })

  it('confirming calls the delete-account mutation', () => {
    render(<DeleteAccountModal onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /^delete account$/i }))
    expect(mockDeleteAccount).toHaveBeenCalledOnce()
  })

  it('on success: clears auth and redirects to /', () => {
    render(<DeleteAccountModal onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /^delete account$/i }))
    const opts = mockDeleteAccount.mock.calls[0][0]
    opts.onSuccess()
    expect(mockClearAuth).toHaveBeenCalledOnce()
    expect(mockRouterPush).toHaveBeenCalledWith('/')
  })

  it('on API error: keeps modal open and shows error message', async () => {
    render(<DeleteAccountModal onClose={vi.fn()} />)
    fireEvent.click(screen.getByRole('button', { name: /^delete account$/i }))
    const opts = mockDeleteAccount.mock.calls[0][0]
    opts.onError({ detail: 'Could not revoke a Google token — please try again in a moment.' })
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/could not revoke a google token/i)
    })
    // Still open
    expect(screen.getByText('Delete your account')).toBeInTheDocument()
    // Did not redirect
    expect(mockRouterPush).not.toHaveBeenCalled()
    expect(mockClearAuth).not.toHaveBeenCalled()
  })
})
