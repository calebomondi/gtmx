import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArchiveRestore,
  ArrowLeft,
  FolderRoot,
  Sparkles,
  Trash2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { cn } from '@/lib/utils'
import { getWorkspace, workspaceDisplayName, type WorkspaceDetail } from '@/lib/api'
import {
  deleteArchivedWorkspace,
  restoreWorkspaceAction,
} from '@/lib/workspaces-store'
import {
  refetchProjects,
  useProjects,
} from '@/lib/projects-store'

const STAMP_CLASSES =
  'font-mono text-[10px] tracking-[0.14em] text-amber-500/90 uppercase'

function archivedStamp(date: string | null): string {
  if (!date) return 'ARCHIVED'
  const parsed = new Date(date)
  if (Number.isNaN(parsed.getTime())) return 'ARCHIVED'
  return parsed
    .toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    .toUpperCase()
}

export function ArchivedWorkspace() {
  const { workspace_id: workspaceIdParam } = useParams<{ workspace_id: string }>()
  const navigate = useNavigate()

  const [workspace, setWorkspace] = useState<WorkspaceDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [busy, setBusy] = useState(false)

  const { projects, archivedProjects } = useProjects()
  const projectName = workspace?.project_id
    ? [...projects, ...archivedProjects].find(
        (project) => project.id === workspace.project_id,
      )?.name ?? null
    : null

  const load = useCallback(async () => {
    if (!workspaceIdParam) return
    setLoading(true)
    setLoadError(null)
    try {
      const detail = await getWorkspace(workspaceIdParam)
      setWorkspace(detail)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [workspaceIdParam])

  useEffect(() => {
    void load()
  }, [load])

  useEffect(() => {
    if (workspace && !workspace.archived) {
      // Not actually archived — send it to the normal workspace view.
      navigate(`/workspace/${workspace.id}`, { replace: true })
    }
  }, [workspace, navigate])

  const handleRestore = async () => {
    if (!workspace) return
    setBusy(true)
    try {
      await restoreWorkspaceAction(workspace.id)
      toast.success('Workspace restored', {
        description: `${workspaceDisplayName(workspace)} is live again.`,
      })
      await refetchProjects()
      navigate(`/workspace/${workspace.id}`, { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!workspace) return
    setBusy(true)
    try {
      await deleteArchivedWorkspace(workspace.id)
      toast.success('Workspace deleted')
      navigate('/archive', { replace: true })
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const profile = workspace?.product_profile

  return (
    <div className="bg-muted flex min-h-0 flex-1 flex-col">
      {/* Sticky header */}
      <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur">
        <div className="flex min-w-0 items-center gap-2 px-4">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            aria-label="Back to archive"
            className="cursor-pointer"
            onClick={() => navigate('/archive')}
          >
            <ArrowLeft className="size-4" />
          </Button>
          <span className={STAMP_CLASSES}>Archived · {archivedStamp(workspace?.archived_at ?? null)}</span>
          <span className="text-muted-foreground hidden truncate text-sm sm:inline">
            {workspace ? workspaceDisplayName(workspace) : '…'}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-2 px-4">
          {projectName && (
            <span className="inline-flex items-center gap-1 rounded-full border border-primary/10 bg-muted/60 px-2 py-0.5 text-[11px] font-medium">
              <FolderRoot className="size-3" />
              {projectName}
            </span>
          )}
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer rounded-md border-amber-500/40 text-amber-500 hover:bg-amber-500/10 hover:text-amber-500"
            disabled={busy}
            onClick={() => void handleRestore()}
          >
            <ArchiveRestore className="size-3.5" />
            Restore
          </Button>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="cursor-pointer text-destructive hover:text-destructive"
            disabled={busy}
            onClick={() => setDeleteOpen(true)}
          >
            <Trash2 className="size-3.5" />
          </Button>
        </div>
      </header>

      {loadError ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="max-w-sm text-center">
            <p className="text-sm font-medium text-foreground">Couldn't open this file</p>
            <p className="mt-1 text-sm text-muted-foreground">{loadError}</p>
          </div>
        </div>
      ) : loading || !workspace ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Opening archived workspace…
        </div>
      ) : (
        <div className="mx-auto w-full min-h-0 max-w-2xl flex-1 space-y-4 overflow-y-auto p-6">
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/[0.06] px-4 py-3">
            <p className="text-sm font-medium text-amber-600">
              Read-only snapshot
            </p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              This workspace is archived — agents aren't watching it anymore. Restore
              it to reopen the full experience.
            </p>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                {workspaceDisplayName(workspace)}
              </CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm">
              <Row label="Agent name" value={workspace.name} />
              <Row label="Product/service" value={workspace.product_name} />
              <Row label="Created" value={formatDate(workspace.date_created)} />
              <Row label="Last activity" value={formatDate(workspace.last_activity)} />
            </CardContent>
          </Card>

          {profile && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="flex items-center gap-2 text-base">
                  <Sparkles className="size-4 text-amber-500" />
                  What the agent understood
                </CardTitle>
              </CardHeader>
              <CardContent className="grid gap-3 text-sm">
                <Row label="Description" value={profile.product_description} />
                <Row label="Problem solved" value={profile.problem_solved} />
                <Row label="How it works" value={profile.how_it_works} />
                <Row label="Intent" value={profile.intent} />
                {profile.features.length > 0 && (
                  <div>
                    <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                      Features
                    </p>
                    <ul className="mt-1.5 grid gap-1.5">
                      {profile.features.map((feature) => (
                        <li
                          key={feature.id}
                          className="rounded-md border border-primary/10 bg-muted/50 px-3 py-2"
                        >
                          <p className="text-sm font-medium">{feature.name}</p>
                          {feature.description && (
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {feature.description}
                            </p>
                          )}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Delete forever confirm */}
      <Dialog open={deleteOpen} onOpenChange={(open) => !open && setDeleteOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              Delete “{workspace ? workspaceDisplayName(workspace) : '…'}” forever?
            </DialogTitle>
            <DialogDescription>
              This can't be undone — the archived record will be gone permanently.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void handleDelete()} disabled={busy}>
              <Trash2 className="size-4" />
              Delete forever
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function Row({ label, value }: { label: string; value: string | null | undefined }) {
  if (!value) return null
  return (
    <div className="grid grid-cols-[110px_1fr] gap-3">
      <p className={cn('text-xs font-medium tracking-wide text-muted-foreground uppercase')}>
        {label}
      </p>
      <p className="min-w-0 break-words text-sm text-foreground">{value}</p>
    </div>
  )
}

function formatDate(value: string | null): string {
  if (!value) return '—'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

export default ArchivedWorkspace