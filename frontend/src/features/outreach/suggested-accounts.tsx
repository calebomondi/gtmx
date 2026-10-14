import { Check, Swords, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import type { AccountRecord } from '@/lib/api'

export type ReviewChoice = 'target' | 'dismissed'

/** Competitors' clients the agent suggests. They join the targets only when
 * the user accepts them. */
export function SuggestedAccounts({
  accounts,
  onReview,
  onOpenDetail,
}: {
  accounts: AccountRecord[]
  onReview: (account: AccountRecord, choice: ReviewChoice) => void
  onOpenDetail: (account: AccountRecord) => void
}) {
  if (accounts.length === 0) {
    return (
      <p className="py-6 text-center text-xs text-muted-foreground">
        No suggestions right now. Each account run also looks for your competitors' named clients.
      </p>
    )
  }
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        These organizations are named as clients of your competitors, so they already pay for what you sell.
        Accept the ones worth pursuing.
      </p>
      {accounts.map((account) => (
        <div key={account.id} className="flex flex-col gap-2 rounded-lg border border-border p-3">
          <button
            type="button"
            className="flex cursor-pointer flex-col items-start gap-1 text-left"
            onClick={() => onOpenDetail(account)}
          >
            <span className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-medium">{account.name}</span>
              {account.via_competitor_name && (
                <Badge variant="secondary" className="gap-1 font-normal">
                  <Swords className="size-3" />
                  Uses {account.via_competitor_name}
                </Badge>
              )}
            </span>
            {account.fit?.payoff && (
              <span className="text-xs leading-relaxed text-muted-foreground">{account.fit.payoff}</span>
            )}
          </button>
          <div className="flex gap-2">
            <Button
              type="button"
              size="sm"
              className="cursor-pointer bg-amber-500 text-amber-950 hover:bg-amber-400"
              onClick={() => onReview(account, 'target')}
            >
              <Check className="size-3.5" />
              Accept
            </Button>
            <Button type="button" size="sm" variant="ghost" className="cursor-pointer" onClick={() => onReview(account, 'dismissed')}>
              <X className="size-3.5" />
              Dismiss
            </Button>
          </div>
        </div>
      ))}
    </div>
  )
}
