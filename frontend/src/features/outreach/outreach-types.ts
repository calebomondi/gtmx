import type { LucideIcon } from 'lucide-react'

import type { OutreachMessageDto } from '@/lib/api'

export type ChannelGlyph = LucideIcon | string

export type Channel = 'email' | 'linkedin'

export const CHANNELS: Record<Channel, ChannelMeta> = {
  email: { key: 'email', label: 'Email', icon: '/gmail.svg' },
  linkedin: { key: 'linkedin', label: 'LinkedIn', icon: '/linkedin.svg' },
}

export type MessageDirection = 'inbound' | 'outbound'

export type MessageStatus =
  | 'sent'
  | 'opened'
  | 'replied'
  | 'bounced'
  | 'failed'
  | 'draft'

export type ConversationFolder = 'inbox' | 'sent' | 'drafts' | 'bounces'

export interface ChannelMeta {
  key: Channel
  label: string
  icon: ChannelGlyph
}

export interface Connection {
  id: string
  channel: Channel
  label: string
  address: string
}

export interface Contact {
  id: string
  name: string
  company: string
  email?: string
  avatar?: string
}

export interface OutreachMessage {
  id: string
  conversationId: string
  channel: Channel
  direction: MessageDirection
  subject?: string
  body: string
  timestamp: number
  status: MessageStatus
}

export interface Conversation {
  id: string
  channel: Channel
  contact: Contact
  messages: OutreachMessage[]
  folder: ConversationFolder
  unread: boolean
  hot: boolean
  lastActivityAt: number
}

export type OutreachFilter = 'all' | ConversationFolder
export type ChannelFilter = 'all' | Channel

export function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

export function latestMessage(
  conversation: Conversation,
): OutreachMessage | null {
  if (conversation.messages.length === 0) return null
  return conversation.messages[conversation.messages.length - 1]
}

export function snippetFor(conversation: Conversation): string {
  const message = latestMessage(conversation)
  if (!message) return 'No messages yet.'
  const text = message.body.replace(/\s+/g, ' ').trim()
  return text.length > 80 ? `${text.slice(0, 80)}…` : text
}

export function matchContactEmail(
  conversations: Conversation[],
  email?: string,
): Conversation | null {
  if (!email) return null
  const norm = email.trim().toLowerCase()
  return (
    conversations.find(
      (conversation) =>
        conversation.contact.email?.toLowerCase() === norm ||
        conversation.messages.some((message) =>
          message.body.toLowerCase().includes(norm),
        ),
    ) ?? null
  )
}

const FOLDER_OF: Record<OutreachMessageDto['status'], ConversationFolder> = {
  draft: 'drafts',
  sending: 'sent',
  sent: 'sent',
  failed: 'bounces',
  bounced: 'bounces',
  received: 'inbox',
}

/** One outreach message is one conversation until reply sync exists. */
export function toConversation(dto: OutreachMessageDto): Conversation {
  const at = Date.parse(dto.sent_at ?? dto.updated_at)
  return {
    id: dto.id,
    channel: dto.channel,
    contact: {
      id: dto.account_id ?? dto.id,
      name: dto.recipient_name || dto.recipient_company,
      company: dto.recipient_company,
      email: dto.recipient_address ?? undefined,
    },
    messages: [{
      id: dto.id,
      conversationId: dto.id,
      channel: dto.channel,
      direction: dto.direction,
      subject: dto.subject ?? undefined,
      body: dto.body,
      timestamp: at,
      status: dto.status === 'sending' ? 'sent' : dto.status === 'received' ? 'replied' : dto.status,
    }],
    folder: FOLDER_OF[dto.status],
    unread: dto.direction === 'inbound' && dto.read_at === null,
    hot: false,
    lastActivityAt: at,
  }
}
