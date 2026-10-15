import { Badge } from '@/components/ui/badge'
import type { AccountRun } from '@/lib/api'
import { cn } from '@/lib/utils'

function StatusBadge({ status }: { status: AccountRun['status'] }) {
  const tone =
    status === 'completed'
      ? 'bg-emerald-500/15 text-emerald-500'
      : status === 'failed'
        ? 'bg-red-500/15 text-red-500'
        : 'bg-amber-500/15 text-amber-500'
  return (
    <Badge variant="outline" className={cn('border-transparent', tone)}>
      {status}
    </Badge>
  )
}

/** Past account-discovery runs, newest first. */
export function AccountRunsList({ runs }: { runs: AccountRun[] }) {
  if (runs.length === 0) return <p className="py-6 text-center text-xs text-muted-foreground">No account runs yet.</p>
  return (
    <div className="flex flex-col gap-2">
      {runs.map((r) => (
        <div key={r.id} className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2">
          <div className="min-w-0">
            <p className="text-xs font-medium">{new Date(r.created_at).toLocaleString()}</p>
            <p className="text-xs text-muted-foreground">
              {r.found} found · {r.candidates_seen} checked
            </p>
          </div>
          <StatusBadge status={r.status} />
        </div>
      ))}
    </div>
  )
}
