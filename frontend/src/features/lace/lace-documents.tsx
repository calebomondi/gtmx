import { useEffect, useState } from "react"
import { FileText, Loader2, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { deleteLaceDocument, listLaceDocuments, type LaceDocumentDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

function size(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

/** The documents the founder shared with the Lace in its chat, newest
 * first, each removable. The Lace reads them when they bear on a question. */
export function LaceDocuments({ laceId, name }: { laceId: string; name: string }) {
  const [docs, setDocs] = useState<LaceDocumentDto[] | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listLaceDocuments(laceId)
      .then((next) => !cancelled && setDocs(next))
      .catch((err) => !cancelled && setError(message(err)))
    return () => { cancelled = true }
  }, [laceId])

  const remove = async (id: string) => {
    setRemoving(id)
    setError(null)
    try {
      await deleteLaceDocument(laceId, id)
      setDocs((prev) => prev?.filter((d) => d.id !== id) ?? null)
    } catch (err) {
      setError(message(err))
    } finally {
      setRemoving(null)
    }
  }

  if (docs === null && !error) return <Skeleton className="h-10 w-full" />
  return (
    <div className="flex flex-col gap-2">
      {docs?.length === 0 && (
        <p className="text-sm text-muted-foreground">None yet. Attach a deck or a one-pager in the chat and {name} keeps it.</p>
      )}
      <ul className="flex flex-col gap-1.5">
        {docs?.map((doc) => (
          <li key={doc.id} className="flex items-center gap-3 rounded-lg border px-3 py-2">
            <FileText className="size-4 shrink-0 text-theme" />
            <span className="flex min-w-0 flex-1 flex-col">
              <span className="truncate text-sm">{doc.filename}</span>
              <span className="text-xs text-muted-foreground">
                {size(doc.size_bytes)} · {formatRelativeTime(Date.parse(doc.created_at))}
                {doc.truncated && " · only the start was kept"}
              </span>
            </span>
            <Button size="icon-sm" variant="ghost" onClick={() => void remove(doc.id)} disabled={removing !== null}
                    aria-label={`Remove ${doc.filename}`}>
              {removing === doc.id ? <Loader2 className="animate-spin" /> : <Trash2 />}
            </Button>
          </li>
        ))}
      </ul>
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
    </div>
  )
}
