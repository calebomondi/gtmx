import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { ArchiveRestore, Loader2, RotateCcw } from "lucide-react"

import { Button } from "@/components/ui/button"
import { retryLaceOnboarding, type LaceDto } from "@/lib/api"
import { restoreLace } from "@/lib/laces-store"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** Above an archived Lace (with Restore) or one whose setup stopped before
 * it read the site (with Try again); nothing otherwise. */
export function LaceStatusBanner({ lace, working, onChanged }: {
  lace: LaceDto | null
  working: boolean
  onChanged: () => void
}) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  if (!lace || working || lace.status === "active") return null
  const archived = lace.status === "archived"

  const act = async () => {
    setBusy(true)
    setError(null)
    try {
      if (archived) {
        await restoreLace(lace.id)
        onChanged()
      } else {
        const { run_id } = await retryLaceOnboarding(lace.id)
        navigate(`/lace/${lace.id}/setup?run=${run_id}`)
      }
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-b bg-muted/50 px-4 py-2 text-sm" role="status">
      <span>
        {archived ? `${lace.name} is archived and isn't doing any work.` : `${lace.name} didn't finish reading your site.`}
        {error && <span className="ml-2 text-destructive">{error}</span>}
      </span>
      {/* Only its owner restores an archived Lace. */}
      {(!archived || lace.role === "owner") && (
        <Button size="sm" variant="outline" onClick={() => void act()} disabled={busy}>
          {busy ? <Loader2 className="animate-spin" /> : archived ? <ArchiveRestore /> : <RotateCcw />}
          {archived ? "Restore" : "Try again"}
        </Button>
      )}
    </div>
  )
}
