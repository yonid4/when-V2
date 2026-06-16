import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockDisconnect = vi.fn()
const mockUpdateSource = vi.fn()
const mockSync = vi.fn()

vi.mock('@/hooks/useCalendarAccounts', () => ({
  useCalendarAccounts: vi.fn(),
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

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => '/settings',
  useSearchParams: () => ({ get: vi.fn().mockReturnValue(null) }),
}))

import { useCalendarAccounts } from '@/hooks/useCalendarAccounts'
import SettingsPage from '@/app/settings/page'

const mockAccount = {
  id: 'account-1',
  user_id: 'user-1',
  provider: 'google',
  provider_email: 'alice@gmail.com',
  provider_account_id: 'google-id-1',
  connected_at: new Date().toISOString(),
  last_synced_at: null,
  sources: [
    {
      id: 'source-1',
      account_id: 'account-1',
      calendar_id: 'alice@gmail.com',
      calendar_name: 'Primary',
      is_enabled: true,
      is_write_calendar: true,
      is_writable: true,
      color: '#9b4428',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
}

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders heading', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [], isLoading: false } as any)
    render(<SettingsPage />)
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' })).toBeInTheDocument()
  })

  it('shows loading state', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: undefined, isLoading: true } as any)
    render(<SettingsPage />)
    expect(screen.getByText(/loading accounts/i)).toBeInTheDocument()
  })

  it('shows empty state when no accounts', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [], isLoading: false } as any)
    render(<SettingsPage />)
    expect(screen.getByText(/no calendars connected/i)).toBeInTheDocument()
  })

  it('renders connected account with email', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
    render(<SettingsPage />)
    expect(screen.getByText('alice@gmail.com')).toBeInTheDocument()
    expect(screen.getByText('google Calendar')).toBeInTheDocument()
  })

  it('renders calendar source toggle', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
    render(<SettingsPage />)
    expect(screen.getByText('Primary')).toBeInTheDocument()
    const checkbox = screen.getByRole('checkbox')
    expect(checkbox).toBeChecked()
  })

  it('calls disconnect when Disconnect button clicked', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
    render(<SettingsPage />)
    fireEvent.click(screen.getByText('Disconnect'))
    expect(mockDisconnect).toHaveBeenCalledWith('account-1')
  })

  it('calls updateSource when toggle changed', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
    render(<SettingsPage />)
    fireEvent.click(screen.getByRole('checkbox'))
    expect(mockUpdateSource).toHaveBeenCalledWith({
      sourceId: 'source-1',
      data: { is_enabled: false },
    })
  })

  it('calls sync when Sync Now button clicked', () => {
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
    render(<SettingsPage />)
    fireEvent.click(screen.getByText('Sync Now'))
    expect(mockSync).toHaveBeenCalled()
  })
})
