import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

vi.mock('@/lib/api', () => ({
  api: {
    get: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  },
}))

import { api } from '@/lib/api'
import {
  useCalendarAccounts,
  useDisconnectCalendarAccount,
  useUpdateCalendarSource,
} from '@/hooks/useCalendarAccounts'

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return React.createElement(QueryClientProvider, { client: queryClient }, children)
}

const mockAccount = {
  id: 'account-1',
  user_id: 'user-1',
  provider: 'google',
  provider_email: 'alice@gmail.com',
  provider_account_id: 'google-id-1',
  connected_at: new Date().toISOString(),
  last_synced_at: null,
  sources: [],
}

describe('useCalendarAccounts', () => {
  beforeEach(() => vi.clearAllMocks())

  it('fetches calendar accounts', async () => {
    vi.mocked(api.get).mockResolvedValue([mockAccount])
    const { result } = renderHook(() => useCalendarAccounts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([mockAccount])
    expect(api.get).toHaveBeenCalledWith('/calendar-accounts')
  })

  it('returns empty array when no accounts', async () => {
    vi.mocked(api.get).mockResolvedValue([])
    const { result } = renderHook(() => useCalendarAccounts(), { wrapper })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual([])
  })
})

describe('useDisconnectCalendarAccount', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls DELETE endpoint', async () => {
    vi.mocked(api.get).mockResolvedValue([mockAccount])
    vi.mocked(api.delete).mockResolvedValue(undefined)
    const { result } = renderHook(
      () => ({
        accounts: useCalendarAccounts(),
        disconnect: useDisconnectCalendarAccount(),
      }),
      { wrapper }
    )
    result.current.disconnect.mutate('account-1')
    await waitFor(() => expect(api.delete).toHaveBeenCalledWith('/calendar-accounts/account-1'))
  })
})

describe('useUpdateCalendarSource', () => {
  beforeEach(() => vi.clearAllMocks())

  it('calls PATCH endpoint with correct payload', async () => {
    vi.mocked(api.get).mockResolvedValue([mockAccount])
    const updatedSource = {
      id: 'source-1',
      account_id: 'account-1',
      calendar_id: 'alice@gmail.com',
      calendar_name: 'Primary',
      is_enabled: false,
      is_write_calendar: true,
    }
    vi.mocked(api.patch).mockResolvedValue(updatedSource)
    const { result } = renderHook(
      () => ({
        accounts: useCalendarAccounts(),
        update: useUpdateCalendarSource(),
      }),
      { wrapper }
    )
    result.current.update.mutate({ sourceId: 'source-1', data: { is_enabled: false } })
    await waitFor(() =>
      expect(api.patch).toHaveBeenCalledWith('/calendar-sources/source-1', { is_enabled: false })
    )
  })
})
