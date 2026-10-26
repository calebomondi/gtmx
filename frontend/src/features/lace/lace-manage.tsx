import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Archive, ArchiveRestore, Loader2, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import type { LaceStatus } from "@/lib/api"
import { archiveLace, deleteLace, restoreLace } from "@/lib/laces-store"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** Archive a Lace (kept whole, restorable) or restore it, and delete it for
 * good behind a confirmation. `onChanged` reloads the open Lace. */
export function LaceManage({ laceId, name, status, onChanged }: {
  laceId: string
  name: string
  status: LaceStatus
  onChanged: () => void
}) {
  const navigate = useNavigate()
  const [busy, setBusy] = useState<"archive" | "delete" | null>(null)
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const archived = status === "archived"

  const toggleArchive = async () => {
    setBusy("archive")
    setError(null)
    try {
      await (archived ? restoreLace(laceId) : archiveLace(laceId))
      onChanged()
    } catch (err) {
      setError(message(err))
    } finally {
      setBusy(null)
    }
  }

  const remove = async () => {
    setBusy("delete")
    setError(null)
    try {
      await deleteLace(laceId)
      navigate("/", { replace: true })
    } catch (err) {
      setConfirming(false)
      setError(message(err))
      setBusy(null)
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted-foreground">
        {archived
          ? `${name} is archived: it does no work and isn't in your crew. Restore it to pick up where it left off.`
          : `Archiving puts ${name} away with everything it knows; you can restore it any time.`}
      </p>
      <div className="flex flex-wrap gap-2">
        <Button variant="outline" size="sm" onClick={() => void toggleArchive()} disabled={busy !== null}>
          {busy === "archive" ? <Loader2 className="animate-spin" /> : archived ? <ArchiveRestore /> : <Archive />}
          {archived ? "Restore" : "Archive"}
        </Button>
        <Button variant="destructive" size="sm" onClick={() => setConfirming(true)} disabled={busy !== null}>
          <Trash2 /> Delete
        </Button>
      </div>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      <Dialog open={confirming} onOpenChange={(open) => !busy && setConfirming(open)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {name}?</DialogTitle>
            <DialogDescription>
              Everything {name} knows, found and wrote goes with it, conversations included. This can't be undone.
              {!archived && " To keep it, archive it instead."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose render={<Button variant="outline" disabled={busy !== null} />}>Cancel</DialogClose>
            <Button variant="destructive" onClick={() => void remove()} disabled={busy !== null}>
              {busy === "delete" && <Loader2 className="animate-spin" />} Delete {name}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
