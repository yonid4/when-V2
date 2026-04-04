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
  google_calendar_event_id: string | null
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

export interface CalendarAccount {
  id: string
  user_id: string
  provider: string
  provider_email: string
  provider_account_id: string
  connected_at: string
  last_synced_at: string | null
  sources: CalendarSource[]
}

export interface CalendarSource {
  id: string
  account_id: string
  calendar_id: string
  calendar_name: string
  is_enabled: boolean
  is_write_calendar: boolean
  color: string | null
  created_at: string
  updated_at: string
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
