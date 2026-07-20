// ─── Profiles ────────────────────────────────────────────────────────────────

export interface User {
  id: string
  full_name: string | null
  avatar_url: string | null
  email_address: string
  timezone: string | null
  primary_calendar_provider: string | null
  created_at: string
  updated_at: string
}

// ─── Events ──────────────────────────────────────────────────────────────────

export type EventType = 'meeting' | 'social' | 'birthday' | 'other'
export type EventStatus = 'planning' | 'confirmed' | 'cancelled'

export interface Event {
  id: string
  uid: string
  name: string
  description: string | null
  event_type: EventType
  coordinator_id: string
  earliest_datetime_utc: string
  latest_datetime_utc: string
  duration_minutes: number
  status: EventStatus
  location: string | null
  video_call_link: string | null
  finalized_start_time_utc: string | null
  finalized_end_time_utc: string | null
  allow_guest_invites: boolean
  calendar_event_id: string | null
  proposals_needs_regeneration: boolean
  proposals_last_generated_at: string | null
  created_at: string
  updated_at: string
  finalized_at: string | null
}

export interface EventWithParticipants extends Event {
  participants: Participant[]
}

// ─── Participants ─────────────────────────────────────────────────────────────

export type ParticipantStatus = 'invited' | 'accepted' | 'declined' | 'maybe'
export type RsvpStatus = 'pending' | 'going' | 'maybe' | 'not_going'

export interface Participant {
  event_id: string
  user_id: string
  status: ParticipantStatus
  rsvp_status: RsvpStatus | null
  can_invite: boolean
  joined_at: string
  // Joined from profiles:
  full_name: string | null
  avatar_url: string | null
  email_address: string | null
}

// ─── Invitations ──────────────────────────────────────────────────────────────

export type InvitationStatus = 'pending' | 'accepted' | 'declined'

export interface Invitation {
  id: string
  event_id: string
  inviter_id: string
  invitee_id: string | null
  invitee_email: string
  status: InvitationStatus
  created_at: string
  updated_at: string
}

// ─── Notifications ────────────────────────────────────────────────────────────

export type NotificationType =
  | 'event_invitation'
  | 'invite_accepted'
  | 'event_finalized'
  | 'event_deleted'
  | 'event_time_changed'

export interface Notification {
  id: string
  user_id: string
  event_id: string | null
  event_uid: string | null
  notification_type: NotificationType
  title: string
  message: string
  is_read: boolean
  action_taken: boolean
  action_type: string | null
  metadata: Record<string, unknown> | null
  created_at: string
  read_at: string | null
  action_at: string | null
}

// ─── Calendar ─────────────────────────────────────────────────────────────────

export type CalendarProvider = 'google' | 'microsoft'

export interface CalendarAccount {
  id: string
  user_id: string
  provider: CalendarProvider
  provider_email: string
  provider_account_id: string
  connected_at: string
  last_synced_at: string | null
  needs_reauth: boolean
  sources: CalendarSource[]
}

export interface CalendarSource {
  id: string
  account_id: string
  calendar_id: string
  calendar_name: string
  is_enabled: boolean
  is_write_calendar: boolean
  is_writable: boolean
  color: string | null
  created_at: string
  updated_at: string
}

// ─── Proposed time notes ──────────────────────────────────────────────────────

export interface ProposedTimeNote {
  id: string
  proposed_time_id: string
  user_id: string
  content: string
  created_at: string
}

// ─── Slots ────────────────────────────────────────────────────────────────────

export interface BusySlot {
  id: string
  user_id: string
  calendar_source_id: string
  provider_event_id: string
  start_time_utc: string
  end_time_utc: string
  last_synced_at: string
  created_at: string
  updated_at: string
}

export interface PreferredSlot {
  id: string
  user_id: string
  event_id: string
  start_time_utc: string
  end_time_utc: string
  created_at: string
}

export interface ProposedTime {
  id: string
  event_id: string
  start_time_utc: string
  end_time_utc: string
  conflicts: number
  reasoning: string
  rank: number
  created_at: string
}

export interface ProposalResponse {
  id: string
  event_id: string
  start_time_utc: string
  end_time_utc: string
  conflict_count: number
  preferred_count: number
  reasoning: string
  rank: number
}

// ─── Event creation wizard ────────────────────────────────────────────────────

export interface Step1Values {
  name: string
  event_type: 'meeting' | 'social' | 'birthday' | 'other'
  description?: string
  location?: string
  video_call_link?: string
}

export interface Step2Values {
  earliest_date: string
  latest_date: string
  start_time: string
  end_time: string
  duration_minutes: number
  participant_emails: string[]
}

export interface WizardData {
  step1: Step1Values
  step2: Step2Values
}

// ─── Availability segments (pre-computed by backend) ─────────────────────────

export type AvailabilitySegmentType = 'busy' | 'preferred' | 'conflict'

export interface AvailabilitySegment {
  start_time_utc: string
  end_time_utc: string
  type: AvailabilitySegmentType
  busy_count: number
  preferred_count: number
}


// ─── Finalization ─────────────────────────────────────────────────────────────

export interface FinalizeStatus {
  status: string
  finalized_start_time_utc: string | null
  finalized_end_time_utc: string | null
  calendar_event_id: string | null
  location: string | null
  video_call_link: string | null
}

export interface FinalizeBody {
  proposed_time_id: string
  name: string
  excluded_user_ids: string[]
  extra_emails: string[]
  note: string
  location: string
  video_call_link: string
}

// ─── Edit mode ────────────────────────────────────────────────────────────────

export interface PendingSlot {
  dayIndex: number
  startUtc: Date
  endUtc: Date
}

export interface MergeResult {
  pendingSlot: PendingSlot
  slotsToDelete: string[]
  remainingSlots: PreferredSlot[]
}

// ─── Popover ──────────────────────────────────────────────────────────────────

export interface PopoverContextValue {
  open: boolean
  setOpen: (open: boolean) => void
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export type ChatThreadStatus =
  | 'idle'
  | 'collecting'
  | 'awaiting_email'
  | 'awaiting_choice'
  | 'awaiting_confirmation'

export type ChatRole = 'user' | 'assistant'
export type ChatWorkflow = 'create_event' | 'edit_event'

export type ChatActionType =
  | 'book_direct'
  | 'use_in_app'
  | 'confirm_draft'
  | 'cancel'
  | 'provide_email'
  | 'pick_person'

export type DraftMode = 'create_direct' | 'create_in_app' | 'edit'

export interface ChatPageContext {
  page: string
  event_uid?: string | null
}

export interface DraftEdits {
  title?: string | null
  duration_minutes?: number | null
  location?: string | null
}

export interface ChatActionPayload {
  type: ChatActionType
  email?: string | null
  person_name?: string | null
  user_id?: string | null
  slot_index?: number | null
  edits?: DraftEdits | null
}

// Exactly one of `message` / `action` is sent; `message` is ≤2000 chars
// (enforced server-side). `timezone` is the browser IANA timezone, attached
// automatically by useSendChatTurn.
export interface ChatTurnRequest {
  message?: string
  action?: ChatActionPayload
  context?: ChatPageContext
  timezone?: string | null
}

export interface DraftCardParticipant {
  name?: string | null
  email: string
  in_system: boolean
  has_calendar: boolean
  user_id?: string | null
}

export interface DraftCardSlot {
  start_time_utc: string
  end_time_utc: string
  conflict_count: number
  free_count: number
  total: number
  reasoning: string
}

// `from` mirrors the literal jsonb key emitted by the backend.
export interface EditChange {
  field: string
  label: string
  from?: string | number | null
  to?: string | number | null
}

export interface DraftCard {
  mode: DraftMode | null
  title: string
  event_type?: string | null
  earliest_datetime_utc?: string | null
  latest_datetime_utc?: string | null
  duration_minutes?: number | null
  participants: DraftCardParticipant[]
  slots: DraftCardSlot[]
  changes?: EditChange[] | null
  event_uid?: string | null
}

export interface ChatButton {
  label: string
  action: ChatActionPayload
}

// Shape of `ChatMessage.payload` for assistant messages.
export interface ChatAssistantPayload {
  card?: DraftCard | null
  buttons: ChatButton[]
}

export interface ChatMessage {
  id: string
  thread_id: string
  role: ChatRole
  content: string
  payload?: ChatAssistantPayload | null
  created_at: string
}

export interface ChatThread {
  id: string
  title?: string | null
  status: ChatThreadStatus
  workflow?: ChatWorkflow | null
  last_event_uid?: string | null
  created_at: string
  updated_at: string
}

export interface ChatTurnResponse {
  thread: ChatThread
  messages: ChatMessage[]
  event_uid?: string | null
}
