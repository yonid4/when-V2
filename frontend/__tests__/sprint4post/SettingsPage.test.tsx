/**
 * Sprint 4 (Post) — SettingsPage write-calendar radio test
 *
 * Focused test: clicking the "Write calendar" radio calls updateSource.mutate
 * with { sourceId, data: { is_write_calendar: true } }
 */
import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─── vi.mock calls must appear before any imports that reference mocked modules ──

const mockUpdateSource = vi.fn()

vi.mock('@/hooks/useCalendarAccounts', () => ({
  useCalendarAccounts: vi.fn(),
  useDisconnectCalendarAccount: () => ({ mutate: vi.fn(), isPending: false }),
  useUpdateCalendarSource: () => ({ mutate: mockUpdateSource, isPending: false }),
  useConnectCalendarAccount: () => vi.fn(),
}))

vi.mock('@/hooks/useBusySlots', () => ({
  useSyncMyCalendar: () => ({ mutate: vi.fn(), isPending: false }),
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
      is_write_calendar: false,
      color: '#9b4428',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ],
}

describe('SettingsPage — write-calendar radio', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(useCalendarAccounts).mockReturnValue({ data: [mockAccount], isLoading: false } as any)
  })

  it('calls updateSource with is_write_calendar: true when radio is changed', () => {
    render(<SettingsPage />)

    const radio = screen.getByRole('radio', { name: /write calendar/i })
    radio.click()

    expect(mockUpdateSource).toHaveBeenCalledWith({
      sourceId: 'source-1',
      data: { is_write_calendar: true },
    })
  })
})
