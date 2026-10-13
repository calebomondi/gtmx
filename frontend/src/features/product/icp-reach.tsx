import { ArrowUpRight } from 'lucide-react'

import type { BuyerPersonaDto, TargetChannelDto } from '@/lib/api'
import { VENUE_GROUP_LABEL, VENUE_GROUPS, venueGroupOfChannel } from '@/lib/buyer-type'

import { TagPills } from './product-sections'
import type { VenuesByGroup } from './use-venue-accounts'

// Enough to recognise the group at a glance; the full list is in Reach Out.
const VENUES_SHOWN = 4

/** Who buys a consumer offer: the kinds of people, not companies. */
export function BuyerPersonas({ personas }: { personas: BuyerPersonaDto[] }) {
  if (personas.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] font-medium tracking-wide text-foreground uppercase">Who buys</span>
      {personas.map((persona) => (
        <div key={persona.name} className="flex flex-col gap-1.5 rounded-lg border border-primary/10 p-2.5">
          <p className="text-sm font-semibold text-foreground">{persona.name}</p>
          <p className="text-sm text-muted-foreground">{persona.who}</p>
          {persona.where_they_congregate.length > 0 && <TagPills items={persona.where_they_congregate} />}
        </div>
      ))}
    </div>
  )
}

/** Where to reach them, in the three groups each with its own kind of pitch:
 * the venues the ICP calls for, and the ones account discovery actually found. */
export function ReachGroups({
  channels,
  venues,
  onOpenReachOut,
}: {
  channels: TargetChannelDto[]
  venues: VenuesByGroup
  onOpenReachOut?: () => void
}) {
  return (
    <div className="flex flex-col gap-2">
      <span className="text-[11px] font-medium tracking-wide text-foreground uppercase">Where to reach them</span>
      <div className="grid gap-2 sm:grid-cols-3">
        {VENUE_GROUPS.map((group) => {
          const planned = channels.filter((c) => venueGroupOfChannel(c.channel_type) === group)
          const found = venues[group]
          return (
            <div key={group} className="flex min-w-0 flex-col gap-2 rounded-lg border border-primary/10 p-2.5">
              <p className="text-sm font-semibold text-foreground">
                {VENUE_GROUP_LABEL[group]} <span className="font-normal text-muted-foreground tabular-nums">· {found.length} found</span>
              </p>
              {found.length > 0 ? (
                <ul className="flex flex-col gap-1 text-sm">
                  {found.slice(0, VENUES_SHOWN).map((venue) => (
                    <li key={venue.id} className="truncate">
                      {venue.name}
                      {venue.platform && <span className="text-muted-foreground"> · {venue.platform}</span>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted-foreground">None found yet. Find accounts in Reach Out.</p>
              )}
              {planned.length > 0 && (
                <div className="flex flex-col gap-1 border-t border-primary/10 pt-2">
                  <span className="text-[11px] text-muted-foreground">Look for</span>
                  {planned.map((channel) => (
                    <p key={channel.name} className="text-xs text-muted-foreground">
                      <span className="text-foreground">{channel.name}</span> · {channel.first_angle}
                    </p>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
      {onOpenReachOut && (
        <button
          type="button"
          onClick={onOpenReachOut}
          className="inline-flex w-fit cursor-pointer items-center gap-1 text-xs text-amber-500 hover:underline"
        >
          Open them in Reach Out <ArrowUpRight className="size-3" />
        </button>
      )}
    </div>
  )
}
