import { useCallback, useEffect, useState } from 'react'
import { Loader2, Sparkles } from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import { draftOutreach, listOutreach, type AccountRecord, type OutreachMessageDto } from '@/lib/api'
import { pitchFor } from '@/lib/buyer-type'
import { useSpecialistTeam } from '@/lib/specialists'
import { cn } from '@/lib/utils'

import { REPLY_ONLY_NOTE } from '@/features/connected-accounts/accounts-type'

import { DraftEditor, EDITABLE_STATUSES } from './draft-editor'

type ContactKind = 'email' | 'linkedin' | 'x' | 'instagram' | 'tiktok'

interface ContactChannel {
  kind: ContactKind
  label: string
  address: string
  contactName?: string
}

const PLATFORM_CHANNELS: Record<string, { kind: ContactKind; label: string }> = {
  linkedin: { kind: 'linkedin', label: 'LinkedIn' },
  instagram: { kind: 'instagram', label: 'Instagram' },
  tiktok: { kind: 'tiktok', label: 'TikTok' },
  x: { kind: 'x', label: 'X' },
  twitter: { kind: 'x', label: 'X' },
}

const CHANNEL_ICON: Record<ContactKind, string> = {
  email: '/gmail.svg',
  linkedin: '/linkedin.svg',
  x: '',
  instagram: '/instagram.svg',
  tiktok: '/tiktok.svg',
}

const DRAFTABLE = new Set<ContactKind>(['email', 'linkedin'])
const POLL_MS = 3000

function channelsFor(account: AccountRecord): ContactChannel[] {
  const channels: ContactChannel[] = []
  for (const raw of account.key_contacts) {
    const c = raw as { name?: string; email?: string; linkedin?: string }
    if (typeof c.email === 'string' && c.email) {
      channels.push({ kind: 'email', label: 'Email', address: c.email, contactName: c.name })
    }
    if (typeof c.linkedin === 'string' && c.linkedin) {
      channels.push({ kind: 'linkedin', label: 'LinkedIn', address: c.linkedin, contactName: c.name })
    }
  }
  // The account's own pages: the route when no person is published.
  for (const [platform, url] of Object.entries(account.socials ?? {})) {
    const social = PLATFORM_CHANNELS[platform.toLowerCase()]
    if (social && url && !channels.some((ch) => ch.address === url)) {
      channels.push({ kind: social.kind, label: social.label, address: url, contactName: `${account.name} on ${social.label}` })
    }
  }
  const mapped = PLATFORM_CHANNELS[(account.platform ?? '').toLowerCase()]
  if (mapped && !channels.some((ch) => ch.kind === mapped.kind)) {
    channels.push({ kind: mapped.kind, label: mapped.label, address: account.venue ?? account.name })
  }
  if (channels.length === 0) channels.push({ kind: 'email', label: 'Email', address: '' })
  return channels
}

/** The account's latest editable draft on a channel, and a way to ask the
 *  GTM specialist for a new one (polled until it lands). */
function useAccountDraft(workspaceId: string | undefined, accountId: string | undefined, kind: ContactKind) {
  const [draft, setDraft] = useState<OutreachMessageDto | null>(null)
  const [drafting, setDrafting] = useState(false)

  const load = useCallback(async () => {
    if (!workspaceId || !accountId) return null
    const { messages, drafting_run } = await listOutreach(workspaceId)
    const latest = messages
      .filter((m) => m.account_id === accountId && m.channel === kind && m.direction === 'outbound' && EDITABLE_STATUSES.has(m.status))
      .sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at))[0] ?? null
    setDraft(latest)
    return { latest, running: drafting_run !== null }
  }, [workspaceId, accountId, kind])

  useEffect(() => {
    load().catch(() => undefined)
  }, [load])

  useEffect(() => {
    if (!drafting) return
    const timer = window.setInterval(() => {
      load()
        .then((state) => {
          if (state && !state.running) setDrafting(false)
        })
        .catch(() => setDrafting(false))
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [drafting, load])

  const request = async (channel: ContactChannel) => {
    if (!workspaceId || !accountId || !DRAFTABLE.has(channel.kind)) return
    try {
      await draftOutreach(workspaceId, [accountId], channel.kind as 'email' | 'linkedin', {
        name: channel.contactName,
        address: channel.kind === 'email' ? channel.address || undefined : undefined,
      })
      setDrafting(true)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    }
  }

  return { draft, setDraft, drafting, request }
}

export function AccountDetailDialog({
  workspaceId,
  account,
  open,
  onOpenChange,
  onToggleSelected,
}: {
  workspaceId?: string
  account: AccountRecord | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onToggleSelected: (a: AccountRecord) => void
}) {
  const channels = account ? channelsFor(account) : []
  const [channelIdx, setChannelIdx] = useState(0)
  const channel = channels[Math.min(channelIdx, channels.length - 1)]
  const { draft, setDraft, drafting, request } = useAccountDraft(workspaceId, account?.id, channel?.kind ?? 'email')
  const gtm = useSpecialistTeam(workspaceId)?.find((s) => s.domain === 'gtm')

  if (!account || !workspaceId) return null
  const draftable = channel && DRAFTABLE.has(channel.kind)
  const pitch = pitchFor(account.account_type)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="p-5 sm:max-w-[640px]">
        <DialogHeader className="px-0">
          <DialogTitle className="text-lg">{account.name}</DialogTitle>
          <DialogDescription className="flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="secondary" className="capitalize">{account.account_type}</Badge>
            <Badge variant="outline" className="border-amber-500/40 text-amber-500" title={pitch.hint}>{pitch.label}</Badge>
            {account.industry && <span className="text-muted-foreground">· {account.industry}</span>}
            {account.geo && <span className="text-muted-foreground">· {account.geo}</span>}
            {account.score != null && <span className="text-amber-500">· fit {Math.round(account.score * 100)}%</span>}
          </DialogDescription>
        </DialogHeader>
        {account.summary && <p className="text-sm text-muted-foreground">{account.summary}</p>}

        <div className="mt-2 flex flex-col gap-1.5">
          <p className="text-xs font-medium tracking-wide text-foreground uppercase">Contact</p>
          <div className="flex flex-wrap gap-1.5">
            {channels.map((ch, i) => (
              <button
                key={`${ch.kind}-${ch.address}`}
                type="button"
                aria-pressed={i === channelIdx}
                onClick={() => setChannelIdx(i)}
                className={cn(
                  'flex cursor-pointer items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition-colors',
                  i === channelIdx
                    ? 'border-amber-500 bg-amber-500/10 text-amber-500'
                    : 'border-border bg-secondary/50 text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                )}
              >
                {CHANNEL_ICON[ch.kind] ? (
                  <img src={CHANNEL_ICON[ch.kind]} alt="" className="size-3.5" />
                ) : (
                  <span className="grid size-3.5 place-items-center rounded bg-muted text-[9px] font-bold text-foreground">X</span>
                )}
                <span className="max-w-40 min-w-0 truncate">{ch.contactName ?? (ch.address || ch.label)}</span>
              </button>
            ))}
          </div>
        </div>

        <Separator className="my-2" />

        {account.do_not_contact ? (
          <p className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">
            Someone at {account.name} asked not to be contacted, so your GTM specialist won't draft to them and
            nothing can be sent.
          </p>
        ) : draft ? (
          <DraftEditor
            key={draft.id}
            workspaceId={workspaceId}
            draft={draft}
            onChanged={(m) => setDraft(EDITABLE_STATUSES.has(m.status) ? m : null)}
            onDeleted={() => setDraft(null)}
          />
        ) : draftable ? (
          <div className="flex flex-col items-start gap-2 rounded-lg border border-dashed border-border p-4">
            <p className="text-sm text-muted-foreground">
              {gtm ? `${gtm.name}, your GTM specialist,` : 'Your GTM specialist'} researches {account.name}, picks the
              angle with the rest of the team, and drafts a {channel.label} message for you to review. {pitch.hint} Nothing is sent without you.
            </p>
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400"
              disabled={drafting}
              onClick={() => void request(channel)}
            >
              {drafting ? <Loader2 className="size-3.5 animate-spin" /> : <Sparkles className="size-3.5" />}
              {drafting ? 'Researching and drafting…' : `Ask ${gtm?.name.split(' ')[0] ?? 'the GTM specialist'} to draft`}
            </Button>
          </div>
        ) : (
          <p className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            {(channel && REPLY_ONLY_NOTE[channel.kind]) ?? `${channel?.label} doesn't let apps send cold messages.`}{' '}
            Engage from the {channel?.label} app
            {channel?.address.startsWith('http') && (
              <> (<a href={channel.address} target="_blank" rel="noreferrer" className="text-amber-500 hover:underline">open their page</a>)</>
            )}, or reach this account by email or LinkedIn.
          </p>
        )}

        <div className="flex justify-end">
          <Button type="button" variant="outline" size="sm" className="cursor-pointer" onClick={() => onToggleSelected(account)}>
            {account.selected ? 'Remove from shortlist' : 'Add to shortlist'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}
