import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ArchiveRestore,
  ExternalLink,
  FolderRoot,
  MoreHorizontal,
  Search,
  Trash2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { workspaceDisplayName } from '@/lib/api'
import type { ProjectDto, WorkspaceSummary } from '@/lib/api'
import {
  deleteProjectAction,
  ensureProjectsLoaded,
  refetchProjects,
  restoreProjectAction,
  useProjects,
} from '@/lib/projects-store'
import {
  deleteArchivedWorkspace,
  ensureWorkspacesLoaded,
  refetchWorkspaces,
  restoreWorkspaceAction,
  useWorkspaces,
} from '@/lib/workspaces-store'

type Segment = 'projects' | 'workspaces'

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

function stackedCard(className: string): string {
  return cn('relative overflow-visible border-border/60', className)
}

/** Decorative filing-stack wrapper: folder tab + two offset layers behind. */
function FolderStack({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative">
      <div
        aria-hidden
        className="absolute inset-x-4 -top-2 h-full rounded-lg bg-amber-500/[0.06]"
      />
      <div
        aria-hidden
        className="absolute inset-x-2 -top-1 h-full rounded-lg bg-amber-500/10"
      />
      {/* File tab */}
      <div
        aria-hidden
        className="absolute -top-1.5 left-5 h-2.5 w-14 rounded-t-md border border-b-0 border-primary/10 bg-amber-500/15"
      />
      <div className="relative">{children}</div>
    </div>
  )
}

function ProjectArchiveCard({
  project,
  onRestore,
  onDelete,
}: {
  project: ProjectDto
  onRestore: (project: ProjectDto) => void
  onDelete: (project: ProjectDto) => void
}) {
  const members = project.archived_workspace_count
  return (
    <FolderStack>
      <Card className={stackedCard('p-4')}>
        <div className="flex items-start gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-amber-500/10 text-amber-500">
            <FolderRoot className="size-5" />
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-medium text-foreground">{project.name}</p>
              <span className={STAMP_CLASSES}>{archivedStamp(project.archived_at)}</span>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {members} workspace{members === 1 ? '' : 's'} archived together
              {project.workspace_count > 0 ? ` · ${project.workspace_count} live` : ''}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="cursor-pointer rounded-md border-amber-500/40 text-amber-500 hover:bg-amber-500/10 hover:text-amber-500"
              onClick={() => onRestore(project)}
            >
              <ArchiveRestore className="size-3.5" />
              Restore
            </Button>
            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon-sm"
                    aria-label={`Actions for ${project.name}`}
                  />
                }
              >
                <MoreHorizontal className="size-4" />
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuItem variant="destructive" onSelect={() => onDelete(project)}>
                  <Trash2 className="size-4" />
                  Delete forever
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </Card>
    </FolderStack>
  )
}

function WorkspaceArchiveCard({
  workspace,
  projectName,
  onRestore,
  onOpen,
  onDelete,
}: {
  workspace: WorkspaceSummary
  projectName: string | null
  onRestore: (workspace: WorkspaceSummary) => void
  onOpen: (workspace: WorkspaceSummary) => void
  onDelete: (workspace: WorkspaceSummary) => void
}) {
  return (
    <Card className={stackedCard('p-4')}>
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
          <span className="text-sm font-semibold">
            {workspaceDisplayName(workspace)[0]?.toUpperCase() ?? '?'}
          </span>
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-medium text-foreground">
              {workspaceDisplayName(workspace)}
            </p>
            <span className={STAMP_CLASSES}>{archivedStamp(workspace.archived_at)}</span>
          </div>
          <div className="mt-1 flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            {workspace.product_name && (
              <span className="truncate">{workspace.product_name}</span>
            )}
            {projectName && (
              <span className="inline-flex items-center gap-1 rounded-full border border-primary/10 bg-muted/60 px-1.5 py-0.5 text-[10px] font-medium">
                <FolderRoot className="size-2.5" />
                {projectName}
              </span>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="cursor-pointer rounded-md border-amber-500/40 text-amber-500 hover:bg-amber-500/10 hover:text-amber-500"
            onClick={() => onRestore(workspace)}
          >
            <ArchiveRestore className="size-3.5" />
            Restore
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Actions for ${workspaceDisplayName(workspace)}`}
                />
              }
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem onSelect={() => onOpen(workspace)}>
                <ExternalLink className="size-4" />
                Open read-only
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onSelect={() => onDelete(workspace)}>
                <Trash2 className="size-4" />
                Delete forever
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </Card>
  )
}

function EmptyArchive() {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="relative">
        <div className="flex size-14 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500">
          <ArchiveRestore className="size-6" />
        </div>
      </div>
      <div>
        <p className="text-sm font-medium text-foreground">Nothing archived yet</p>
        <p className="text-muted-foreground mt-1 max-w-sm text-sm">
          Projects and workspaces you archive are filed here so agents stop
          tracking them — anything can be restored later.
        </p>
      </div>
    </div>
  )
}

export function ArchiveComponent() {
  const navigate = useNavigate()
  const { archivedWorkspaces } = useWorkspaces()
  const { archivedProjects, projects } = useProjects()
  const [segment, setSegment] = useState<Segment>('projects')
  const [query, setQuery] = useState('')

  const [restoreTarget, setRestoreTarget] = useState<{
    kind: 'project' | 'workspace'
    id: string
    name: string
    count: number
  } | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<{
    kind: 'project' | 'workspace'
    id: string
    name: string
    count: number
  } | null>(null)
  const [busy, setBusy] = useState(false)
  const [dialogError, setDialogError] = useState<string | null>(null)

  useEffect(() => {
    ensureProjectsLoaded()
    ensureWorkspacesLoaded()
  }, [])

  const q = query.trim().toLowerCase()
  const matches = (name: string) => !q || name.toLowerCase().includes(q)

  const filteredProjects = useMemo(
    () => archivedProjects.filter((project) => matches(project.name)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [archivedProjects, q],
  )
  const filteredWorkspaces = useMemo(
    () =>
      archivedWorkspaces.filter((workspace) =>
        matches(workspaceDisplayName(workspace)),
      ),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [archivedWorkspaces, q],
  )

  const projectNameById = useMemo(() => {
    const map = new Map<string, string>()
    for (const project of [...projects, ...archivedProjects]) {
      map.set(project.id, project.name)
    }
    return map
  }, [projects, archivedProjects])

  const handleRestore = async () => {
    if (!restoreTarget) return
    setBusy(true)
    setDialogError(null)
    try {
      if (restoreTarget.kind === 'project') {
        await restoreProjectAction(restoreTarget.id)
      } else {
        await restoreWorkspaceAction(restoreTarget.id)
      }
      await Promise.all([refetchProjects(), refetchWorkspaces()])
      toast.success('Restored', {
        description:
          restoreTarget.kind === 'project' && restoreTarget.count > 0
            ? `${restoreTarget.name} and its ${restoreTarget.count} workspace${restoreTarget.count === 1 ? '' : 's'} are live again.`
            : `${restoreTarget.name} is back in your workspaces.`,
      })
      setRestoreTarget(null)
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setBusy(true)
    setDialogError(null)
    try {
      if (deleteTarget.kind === 'project') {
        await deleteProjectAction(deleteTarget.id)
      } else {
        await deleteArchivedWorkspace(deleteTarget.id)
      }
      await Promise.all([refetchProjects(), refetchWorkspaces()])
      toast.success('Deleted', {
        description: deleteTarget.kind === 'project'
          ? `${deleteTarget.name} was removed permanently.`
          : 'Workspace removed permanently.',
      })
      setDeleteTarget(null)
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const totalArchived =
    archivedProjects.length + archivedWorkspaces.length

  return (
    <div className="bg-muted flex min-h-0 flex-1 flex-col p-6">
      <div className="mx-auto flex w-full min-h-0 max-w-3xl flex-1 flex-col">
        <div className="mb-4 flex items-start justify-between gap-2">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-medium">Archive</h1>
              <span className={cn(STAMP_CLASSES, 'text-[10px]')}>
                {totalArchived > 0
                  ? `${totalArchived} filed`
                  : 'empty filing cabinet'}
              </span>
            </div>
            <p className="text-muted-foreground mt-0.5 text-sm">
              Archived projects and workspaces — agents no longer track these.
            </p>
          </div>
        </div>

        {totalArchived === 0 ? (
          <EmptyArchive />
        ) : (
          <Tabs
            value={segment}
            onValueChange={(value) => setSegment(value as Segment)}
            className="flex min-h-0 flex-1 flex-col"
          >
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <TabsList>
                <TabsTrigger value="projects">
                  Projects · {archivedProjects.length}
                </TabsTrigger>
                <TabsTrigger value="workspaces">
                  Workspaces · {archivedWorkspaces.length}
                </TabsTrigger>
              </TabsList>
              <div className="relative w-full max-w-64">
                <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search the archive…"
                  className="h-9 bg-muted/60 pl-8 text-sm"
                  aria-label="Search the archive"
                />
              </div>
            </div>

            <hr className="mb-4 border-primary/10" />

            <TabsContent
              value="projects"
              className="min-h-0 flex-1 overflow-y-auto pb-4"
            >
              {filteredProjects.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  No archived projects match your search.
                </p>
              ) : (
                <div className="grid gap-4">
                  {filteredProjects.map((project) => (
                    <ProjectArchiveCard
                      key={project.id}
                      project={project}
                      onRestore={(target) =>
                        setRestoreTarget({
                          kind: 'project',
                          id: target.id,
                          name: target.name,
                          count: target.archived_workspace_count,
                        })
                      }
                      onDelete={(target) =>
                        setDeleteTarget({
                          kind: 'project',
                          id: target.id,
                          name: target.name,
                          count: target.archived_workspace_count,
                        })
                      }
                    />
                  ))}
                </div>
              )}
            </TabsContent>

            <TabsContent
              value="workspaces"
              className="min-h-0 flex-1 overflow-y-auto pb-4"
            >
              {filteredWorkspaces.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">
                  No archived workspaces match your search.
                </p>
              ) : (
                <div className="grid gap-3">
                  {filteredWorkspaces.map((workspace) => (
                    <WorkspaceArchiveCard
                      key={workspace.id}
                      workspace={workspace}
                      projectName={
                        workspace.project_id
                          ? (projectNameById.get(workspace.project_id) ?? null)
                          : null
                      }
                      onRestore={(target) =>
                        setRestoreTarget({
                          kind: 'workspace',
                          id: target.id,
                          name: workspaceDisplayName(target),
                          count: 0,
                        })
                      }
                      onOpen={(target) =>
                        navigate(`/archive/workspace/${target.id}`)
                      }
                      onDelete={(target) =>
                        setDeleteTarget({
                          kind: 'workspace',
                          id: target.id,
                          name: workspaceDisplayName(target),
                          count: 0,
                        })
                      }
                    />
                  ))}
                </div>
              )}
            </TabsContent>
          </Tabs>
        )}
      </div>

      {/* Restore confirm (projects restore the whole group). */}
      <Dialog
        open={restoreTarget !== null}
        onOpenChange={(open) => !open && setRestoreTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Restore “{restoreTarget?.name}”?</DialogTitle>
            <DialogDescription>
              {restoreTarget?.kind === 'project' && (restoreTarget.count ?? 0) > 0 ? (
                <>
                  Its {restoreTarget.count} archived workspace
                  {restoreTarget.count === 1 ? '' : 's'} will be restored with it and
                  agents will start tracking them again.
                </>
              ) : (
                <>It will return to your live workspaces.</>
              )}
            </DialogDescription>
          </DialogHeader>
          {dialogError && <p className="px-4 text-xs text-destructive">{dialogError}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRestoreTarget(null)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              className="bg-[#FEA853] text-black hover:bg-[#FEA853]"
              onClick={() => void handleRestore()}
              disabled={busy}
            >
              <ArchiveRestore className="size-4" />
              Restore
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete forever confirm. */}
      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete “{deleteTarget?.name}” forever?</DialogTitle>
            <DialogDescription>
              {deleteTarget?.kind === 'project' && (deleteTarget.count ?? 0) > 0 ? (
                <>
                  This project still contains {deleteTarget.count} archived workspace
                  {deleteTarget.count === 1 ? '' : 's'}. It must be emptied before it
                  can be deleted.
                </>
              ) : (
                <>
                  This can't be undone — the archived record will be gone permanently.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {dialogError && <p className="px-4 text-xs text-destructive">{dialogError}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteTarget(null)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleDelete()}
              disabled={busy}
            >
              <Trash2 className="size-4" />
              Delete forever
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default ArchiveComponent