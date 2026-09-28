import { Hash, MessagesSquare } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type ChannelGlyph = LucideIcon | string

export type Channel = 'email' | 'linkedin' | 'slack' | 'discord'

export const CHANNELS: Record<Channel, ChannelMeta> = {
  email: { key: 'email', label: 'Email', icon: '/gmail.svg', connected: true },
  linkedin: { key: 'linkedin', label: 'LinkedIn', icon: '/linkedin.svg', connected: true },
  slack: { key: 'slack', label: 'Slack', icon: Hash, connected: false },
  discord: { key: 'discord', label: 'Discord', icon: MessagesSquare, connected: false },
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
  connected: boolean
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

export function formatRelativeTime(timestamp: number): string {
  const diff = Date.now() - timestamp
  const minutes = Math.floor(diff / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days}d ago`
  return new Date(timestamp).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  })
}

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