import { useEffect, useState } from 'react'
import { CalendarCheck, CalendarPlus, Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  addOutreachMeeting,
  draftOutreachReply,
  markOutreachRead,
  type OutreachMessageDto,
} from '@/lib/api'
import { useSpecialistTeam } from '@/lib/specialists'
import { formatRelativeTime } from '@/lib/format'
import { cn } from '@/lib/utils'

import { ChannelGlyph } from './conversation-row'
import { DraftEditor, EDITABLE_STATUSES } from './draft-editor'
import { CHANNELS, initialsFor, type Conversation } from './outreach-types'

const INTENT_LABEL: Record<string, string> = {
  interested: 'Interested',
  question: 'Asked a question',
  objection: 'Objection',
  meeting_request: 'Wants to meet',
  not_now: 'Not now',
  unsubscribe: 'Asked to stop',
  out_of_office: 'Out of office',
  referral: 'Referred you',
}

function errorText(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function MeetingCard({ workspaceId, draft, onChanged }: {
  workspaceId: string
  draft: OutreachMessageDto
  onChanged: (message: OutreachMessageDto) => void
}) {
  const [busy, setBusy] = useState(false)
  const meeting = draft.meeting
  if (!meeting) return null
  const when = new Date(meeting.start).toLocaleString(undefined, { weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
  const add = async () => {
    setBusy(true)
    try {
      onChanged(await addOutreachMeeting(workspaceId, draft.id))
      toast.success('Added to your Google Calendar; the invite went to ' + (meeting.attendee ?? 'the contact'))
    } catch (err) {
      toast.error(errorText(err))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2 text-sm">
      <span>
        <span className="font-medium">{meeting.title}</span>
        <span className="text-muted-foreground"> · {when} ({meeting.timezone})</span>
      </span>
      {meeting.event_url ? (
        <a href={meeting.event_url.startsWith('http') ? meeting.event_url : undefined} target="_blank" rel="noreferrer"
           className="inline-flex shrink-0 items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
          <CalendarCheck className="size-3.5" /> In your calendar
        </a>
      ) : (
        <Button type="button" size="sm" variant="outline" className="shrink-0 cursor-pointer" disabled={busy} onClick={() => void add()}>
          {busy ? <Loader2 className="size-3.5 animate-spin" /> : <CalendarPlus className="size-3.5" />} Add to Google Calendar
        </Button>
      )}
    </div>
  )
}

function Bubble({ message }: { message: OutreachMessageDto }) {
  const inbound = message.direction === 'inbound'
  const when = message.sent_at ? formatRelativeTime(Date.parse(message.sent_at)) : ''
  return (
    <div className={cn('flex flex-col gap-1', inbound ? 'items-start' : 'items-end')}>
      <div
        className={cn(
          'max-w-[85%] whitespace-pre-wrap rounded-lg border px-3 py-2 text-sm',
          inbound ? 'border-border bg-muted/60' : 'border-amber-500/30 bg-amber-500/5',
          message.status === 'bounced' && 'border-destructive/40 bg-destructive/5',
        )}
      >
        {message.subject && !inbound && <p className="mb-1 text-xs font-medium text-muted-foreground">{message.subject}</p>}
        {message.body}
      </div>
      <span className="text-[11px] text-muted-foreground">
        {inbound ? (message.status === 'bounced' ? 'Bounce notice' : message.recipient_name || message.recipient_address) : 'You'}
        {when && ` · ${when}`}
        {inbound && message.intent && INTENT_LABEL[message.intent] && (
          <span className="ml-1.5 rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium text-foreground">
            {INTENT_LABEL[message.intent]}
          </span>
        )}
      </span>
    </div>
  )
}

/** One conversation: what was sent, the replies that came back, and the
 *  draft (if any) to review. Email sends through the user's Gmail on this
 *  button only; LinkedIn is copied and sent by hand. */
export function ThreadModal({
  workspaceId,
  conversation,
  open,
  onOpenChange,
  onChanged,
  onDeleted,
  onDraftRequested,
}: {
  workspaceId?: string
  conversation: Conversation | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged: (message: OutreachMessageDto) => void
  onDeleted: (messageId: string) => void
  /** A reply draft was requested: the parent polls until it lands. */
  onDraftRequested: () => void
}) {
  const gtm = useSpecialistTeam(workspaceId)?.find((s) => s.domain === 'gtm')
  const [requesting, setRequesting] = useState(false)
  const draft = conversation?.dtos.findLast((m) => m.direction === 'outbound' && EDITABLE_STATUSES.has(m.status)) ?? null
  const history = conversation?.dtos.filter((m) => m.id !== draft?.id) ?? []

  // Opening a conversation reads its replies.
  useEffect(() => {
    if (!open || !workspaceId || !conversation) return
    for (const message of conversation.dtos) {
      if (message.direction === 'inbound' && message.read_at === null) {
        markOutreachRead(workspaceId, message.id).then(onChanged).catch(() => undefined)
      }
    }
  }, [open, workspaceId, conversation, onChanged])

  if (!conversation || !workspaceId) return null
  const channel = CHANNELS[conversation.channel]
  const lastReply = conversation.dtos.findLast((m) => m.direction === 'inbound' && m.status === 'received')
  const requestReply = async () => {
    if (!lastReply) return
    setRequesting(true)
    try {
      await draftOutreachReply(workspaceId, lastReply.id)
      toast.success(`${gtm?.name.split(' ')[0] ?? 'Your GTM specialist'} is drafting a reply`)
      onDraftRequested()
    } catch (err) {
      toast.error(errorText(err))
    } finally {
      setRequesting(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader className="border-b">
          <div className="flex items-center gap-3">
            <Avatar size="lg">
              <AvatarFallback>{initialsFor(conversation.contact.name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <DialogTitle className="truncate">{conversation.contact.name}</DialogTitle>
              <DialogDescription className="truncate">
                {conversation.contact.company}
                {draft ? ` · ${draft.thread_id ? 'Reply draft' : 'Draft'} — review before sending` : ''}
              </DialogDescription>
            </div>
            <div className="flex items-center gap-1 rounded-full bg-muted/70 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              <ChannelGlyph icon={channel.icon} className="size-3" />
              {channel.label}
            </div>
          </div>
        </DialogHeader>

        <div className="flex max-h-[65vh] min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-4 py-4">
          {history.map((message) => <Bubble key={message.id} message={message} />)}
          {!draft && conversation.needsReply && (
            <div className="flex justify-end">
              <Button type="button" size="sm" className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400"
                      disabled={requesting} onClick={() => void requestReply()}>
                {requesting ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
                Ask {gtm?.name.split(' ')[0] ?? 'the GTM specialist'} to draft a reply
              </Button>
            </div>
          )}
          {draft && <MeetingCard workspaceId={workspaceId} draft={draft} onChanged={onChanged} />}
          {draft && (
            <DraftEditor
              workspaceId={workspaceId}
              draft={draft}
              onChanged={onChanged}
              onDeleted={(id) => {
                onDeleted(id)
                if (history.length === 0) onOpenChange(false)
              }}
            />
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
