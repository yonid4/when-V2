import { describe, it, expect, beforeEach } from 'vitest'
import { useNotificationStore } from '@/stores/notificationStore'

describe('notificationStore', () => {
  beforeEach(() => {
    useNotificationStore.setState({ unreadCount: 0 })
  })

  it('setCount sets unreadCount to the given value', () => {
    useNotificationStore.getState().setCount(7)
    expect(useNotificationStore.getState().unreadCount).toBe(7)
  })

  it('setCount overwrites a previous non-zero count', () => {
    useNotificationStore.getState().setCount(5)
    useNotificationStore.getState().setCount(2)
    expect(useNotificationStore.getState().unreadCount).toBe(2)
  })

  it('setCount(0) resets to zero', () => {
    useNotificationStore.getState().increment()
    useNotificationStore.getState().setCount(0)
    expect(useNotificationStore.getState().unreadCount).toBe(0)
  })
})
