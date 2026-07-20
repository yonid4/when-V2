import { create } from 'zustand'

// Transient UI state only: whether the chat drawer is open, shared so route
// layouts (currently the event detail page) can reserve space for the drawer
// on desktop instead of being overlaid. No server data lives here.
interface ChatUiState {
  isOpen: boolean
  setOpen: (isOpen: boolean) => void
}

export const useChatUiStore = create<ChatUiState>((set) => ({
  isOpen: false,
  setOpen: (isOpen) => set({ isOpen }),
}))
