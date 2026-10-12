import type { LucideIcon } from 'lucide-react'
import { AtSign } from 'lucide-react'

import type { OutreachMessageDto } from '@/lib/api'

export type ChannelGlyph = LucideIcon | string

/** Outreach channels, one per connectable messaging account. */
export type Channel = 'email' | 'linkedin' | 'instagram' | 'facebook' | 'x'

export interface ChannelMeta {
  key: Channel
  label: string
  icon: ChannelGlyph
  /** The connected-account platform the channel goes out through. */
  platform: string
}

export const CHANNELS: Record<Channel, ChannelMeta> = {
  email: { key: 'email', label: 'Email', icon: '/gmail.svg', platform: 'gmail' },
  linkedin: { key: 'linkedin', label: 'LinkedIn', icon: '/linkedin.svg', platform: 'linkedin' },
  instagram: { key: 'instagram', label: 'Instagram', icon: '/instagram.svg', platform: 'instagram' },
  facebook: { key: 'facebook', label: 'Facebook', icon: '/facebook.svg', platform: 'facebook' },
  x: { key: 'x', label: 'X', icon: AtSign, platform: 'x' },
}

export const CHANNEL_ORDER: Channel[] = ['email', 'linkedin', 'instagram', 'facebook', 'x']

export type MessageDirection = 'inbound' | 'outbound'

export type MessageStatus = 'sent' | 'replied' | 'bounced' | 'failed' | 'draft'

export type ConversationFolder = 'inbox' | 'sent' | 'drafts' | 'bounces'

export type OutreachFilter = 'all' | 'needs_reply' | ConversationFolder
export type ChannelFilter = 'all' | Channel

/** The folders each channel offers: what that channel can actually do.
 *  Email has an inbox and bounces; LinkedIn messages are pasted by hand, so
 *  it only has drafts and what was sent; Instagram and Facebook only allow
 *  answering people who wrote first. */
export const FOLDERS: Record<ChannelFilter, { value: OutreachFilter; label: string }[]> = {
  all: [
    { value: 'all', label: 'All' },
    { value: 'needs_reply', label: 'Needs reply' },
    { value: 'sent', label: 'Sent' },
    { value: 'drafts', label: 'Drafts' },
  ],
  email: [
    { value: 'inbox', label: 'Inbox' },
    { value: 'sent', label: 'Sent' },
    { value: 'drafts', label: 'Drafts' },
    { value: 'bounces', label: 'Bounces' },
  ],
  linkedin: [
    { value: 'drafts', label: 'Drafts' },
    { value: 'sent', label: 'Sent' },
  ],
  instagram: [
    { value: 'inbox', label: 'Inbox' },
    { value: 'sent', label: 'Sent' },
  ],
  facebook: [
    { value: 'inbox', label: 'Inbox' },
    { value: 'sent', label: 'Sent' },
  ],
  x: [
    { value: 'inbox', label: 'Inbox' },
    { value: 'sent', label: 'Sent' },
    { value: 'drafts', label: 'Drafts' },
  ],
}

export interface Contact {
  id: string
  name: string
  company: string
  email?: string
}

export interface OutreachMessage {
  id: string
  direction: MessageDirection
  subject?: string
  body: string
  timestamp: number
  status: MessageStatus
}

/** One thread: what was sent to a contact and everything they sent back. */
export interface Conversation {
  id: string
  channel: Channel
  contact: Contact
  messages: OutreachMessage[]
  /** The raw messages, oldest first, for the thread view. */
  dtos: OutreachMessageDto[]
  folder: ConversationFolder
  unread: boolean
  /** The contact spoke last: the ball is in the user's court. */
  needsReply: boolean
  lastActivityAt: number
}

export function initialsFor(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

export function latestMessage(conversation: Conversation): OutreachMessage | null {
  return conversation.messages.at(-1) ?? null
}

export function snippetFor(conversation: Conversation): string {
  const message = latestMessage(conversation)
  if (!message) return 'No messages yet.'
  const text = message.body.replace(/\s+/g, ' ').trim()
  return text.length > 80 ? `${text.slice(0, 80)}…` : text
}

export function matchContactEmail(conversations: Conversation[], email?: string): Conversation | null {
  if (!email) return null
  const norm = email.trim().toLowerCase()
  return conversations.find((conversation) => conversation.contact.email?.toLowerCase() === norm) ?? null
}

const timeOf = (dto: OutreachMessageDto) => Date.parse(dto.sent_at ?? dto.updated_at)

function statusOf(dto: OutreachMessageDto): MessageStatus {
  if (dto.status === 'received') return 'replied'
  if (dto.status === 'sending') return 'sent'
  return dto.status
}

function folderOf(dtos: OutreachMessageDto[]): ConversationFolder {
  if (dtos.some((m) => m.status === 'bounced' || m.status === 'failed')) return 'bounces'
  if (dtos.some((m) => m.direction === 'inbound')) return 'inbox'
  if (dtos.every((m) => m.status === 'draft')) return 'drafts'
  return 'sent'
}

/** Messages grouped into threads (by provider thread, else one per message). */
export function toConversations(messages: OutreachMessageDto[]): Conversation[] {
  const threads = new Map<string, OutreachMessageDto[]>()
  for (const message of messages) {
    const key = message.thread_id ?? message.id
    threads.set(key, [...(threads.get(key) ?? []), message])
  }
  return [...threads.entries()].map(([id, unsorted]) => {
    const dtos = [...unsorted].sort((a, b) => timeOf(a) - timeOf(b))
    const first = dtos.find((m) => m.direction === 'outbound') ?? dtos[0]
    const last = dtos[dtos.length - 1]
    return {
      id,
      channel: first.channel,
      contact: {
        id: first.account_id ?? first.id,
        name: first.recipient_name || first.recipient_company,
        company: first.recipient_company,
        email: first.recipient_address ?? undefined,
      },
      messages: dtos.map((m) => ({
        id: m.id,
        direction: m.direction,
        subject: m.subject ?? undefined,
        body: m.body,
        timestamp: timeOf(m),
        status: statusOf(m),
      })),
      dtos,
      folder: folderOf(dtos),
      unread: dtos.some((m) => m.direction === 'inbound' && m.read_at === null),
      needsReply: last.direction === 'inbound' && last.status === 'received',
      lastActivityAt: timeOf(last),
    }
  })
}

/** Whether a conversation belongs in the selected channel and folder. */
export function inFolder(conversation: Conversation, channel: ChannelFilter, folder: OutreachFilter): boolean {
  if (channel !== 'all' && conversation.channel !== channel) return false
  if (folder === 'all') return true
  if (folder === 'needs_reply') return conversation.needsReply
  return conversation.folder === folder
}
