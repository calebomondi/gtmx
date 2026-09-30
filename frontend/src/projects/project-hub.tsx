import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Archive,
  ChevronRight,
  Folder,
  Layers,
  MoreHorizontal,
  Pencil,
  Pin,
  Plus,
  Trash2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
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
import { Label } from '@/components/ui/label'
import { SpecialistAvatarGroup } from '@/components/specialist-avatargroup'
import { cn } from '@/lib/utils'
import { getProject, workspaceDisplayName, type ProjectDetailDto } from '@/lib/api'
import {
  archiveProjectAction,
  deleteProjectAction,
  renameProject,
} from '@/lib/projects-store'
import { ActualWorkspace } from '@/sidepanel/actual_workspace'
import { WorkspaceManager } from '@/components/workspace-manager'
import { useWorkspaceSpecialists } from '@/lib/specialists'

export function ProjectHub() {
  const { project_id: projectIdParam, workspace_id: workspaceIdParam } = useParams<{
    project_id: string
    workspace_id?: string
  }>()
  const navigate = useNavigate()

  const [project, setProject] = useState<ProjectDetailDto | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [renameOpen, setRenameOpen] = useState(false)
  const [archiveOpen, setArchiveOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [busy, setBusy] = useState(false)
  const [dialogError, setDialogError] = useState<string | null>(null)

  const load = useCallback(async () => {
    if (!projectIdParam) return
    setLoading(true)
    setLoadError(null)
    try {
      const detail = await getProject(projectIdParam)
      setProject(detail)
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }, [projectIdParam])

  useEffect(() => {
    void load()
  }, [load])

  const liveWorkspaces = (project?.workspaces ?? [])
    .filter((workspace) => !workspace.archived)
    .sort((a, b) => {
      if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
      return new Date(b.last_activity).getTime() - new Date(a.last_activity).getTime()
    })

  const selectedWorkspaceId =
    workspaceIdParam && liveWorkspaces.some((w) => w.id === workspaceIdParam)
      ? workspaceIdParam
      : undefined

  const selectedWorkspace = selectedWorkspaceId
    ? liveWorkspaces.find((w) => w.id === selectedWorkspaceId)
    : undefined

  const showEmptyPick = !selectedWorkspaceId && liveWorkspaces.length > 0

  const handleRename = async () => {
    if (!project) return
    const name = draftName.trim()
    if (!name) {
      setDialogError('Project name cannot be empty.')
      return
    }
    setBusy(true)
    setDialogError(null)
    try {
      await renameProject(project.id, name)
      setRenameOpen(false)
      await load()
      toast.success('Project renamed')
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleArchive = async () => {
    if (!project) return
    setBusy(true)
    setDialogError(null)
    try {
      await archiveProjectAction(project.id)
      setArchiveOpen(false)
      navigate('/projects', { replace: true })
      toast.success('Project archived')
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!project) return
    setBusy(true)
    setDialogError(null)
    try {
      await deleteProjectAction(project.id)
      setDeleteOpen(false)
      navigate('/projects', { replace: true })
      toast.success('Project deleted')
    } catch (err) {
      setDialogError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const memberCount = (project?.workspaces ?? []).length

  return (
    <div className="bg-muted flex min-h-0 flex-1 flex-col">
      {/* Sticky project header */}
      <header className="sticky top-0 z-10 flex h-12 shrink-0 items-center gap-2 border-b bg-background/80 backdrop-blur">
        <div className="flex items-center gap-2 px-4">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem>
                <button
                  type="button"
                  onClick={() => navigate('/projects')}
                  className="cursor-pointer text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
                >
                  Projects
                </button>
              </BreadcrumbItem>
              <BreadcrumbSeparator />
              <BreadcrumbItem>
                <BreadcrumbPage className="flex items-center gap-2">
                  <Folder
                    className={cn(
                      'size-3.5',
                      project?.priority ? 'text-amber-500' : 'text-muted-foreground',
                    )}
                  />
                  <span className="max-w-56 truncate font-medium">
                    {project?.name ?? '…'}
                  </span>
                </BreadcrumbPage>
              </BreadcrumbItem>
              {selectedWorkspace && (
                <>
                  <BreadcrumbSeparator />
                  <BreadcrumbItem>
                    <WorkspaceManager
                      workspace={selectedWorkspace}
                      variant="breadcrumb"
                      onWorkspaceChanged={() => void load()}
                    />
                  </BreadcrumbItem>
                </>
              )}
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        <div className="ml-auto flex items-center gap-2 px-4">
          {project?.priority && (
            <span className="inline-flex items-center gap-1 rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-500">
              Priority
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full border border-primary/10 bg-muted/60 px-2 py-0.5 text-[11px] font-medium tabular-nums">
            {liveWorkspaces.length} live · {memberCount - liveWorkspaces.length} archived
          </span>

          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Actions for ${project?.name ?? 'project'}`}
                />
              }
            >
              <MoreHorizontal className="size-4" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem
                onClick={() => {
                  setDialogError(null)
                  setDraftName(project?.name ?? '')
                  setRenameOpen(true)
                }}
              >
                <Pencil className="size-4" />
                Rename
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setArchiveOpen(true)}>
                <Archive className="size-4" />
                Archive
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem variant="destructive" onClick={() => setDeleteOpen(true)}>
                <Trash2 className="size-4" />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      {loadError ? (
        <div className="flex flex-1 items-center justify-center">
          <div className="max-w-sm text-center">
            <p className="text-sm font-medium text-foreground">Couldn't load this project</p>
            <p className="mt-1 text-sm text-muted-foreground">{loadError}</p>
            <Button variant="outline" className="mt-4" onClick={() => void load()}>
              Try again
            </Button>
          </div>
        </div>
      ) : loading ? (
        <div className="flex flex-1 items-center justify-center text-sm text-muted-foreground">
          Loading project…
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col md:flex-row">
          {/* Workspace rail */}
          <aside className="flex w-full shrink-0 flex-col border-b md:w-72 md:border-r md:border-b-0">
            <div className="flex items-center justify-between px-4 pt-4 pb-2">
              <div>
                <p className="text-xs font-medium tracking-wide text-foreground uppercase">
                  Workspaces
                </p>
                <p className="text-muted-foreground mt-0.5 text-xs">
                  {liveWorkspaces.length} in this project
                </p>
              </div>
              {/* <Button
                type="button"
                size="icon-sm"
                variant="ghost"
                aria-label="New workspace"
                onClick={() => navigate('/new')}
              >
                <Plus className="size-4" />
              </Button> */}
            </div>

            <div className="min-h-0 flex-1 space-y-1 overflow-y-auto px-2 pb-4">
              {liveWorkspaces.length === 0 && (
                <p className="px-2 py-6 text-center text-xs text-muted-foreground">
                  No member workspaces yet.
                  <br />
                  Use “Add to project” from a workspace's menu.
                </p>
              )}
              {liveWorkspaces.map((workspace) => (
                <WorkspaceRailItem
                  key={workspace.id}
                  workspace={workspace}
                  selected={workspace.id === selectedWorkspaceId}
                  onOpen={() =>
                    navigate(`/projects/${project!.id}/workspace/${workspace.id}`)
                  }
                />
              ))}
            </div>
          </aside>

          {/* Main area */}
          <main className="min-h-0 min-w-0 flex-1">
            {selectedWorkspaceId ? (
              <ActualWorkspace workspaceId={selectedWorkspaceId} />
            ) : showEmptyPick ? (
              <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
                  <Layers className="size-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    Pick a workspace to open it
                  </p>
                  <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">
                    {project?.name} has {liveWorkspaces.length} live workspace
                    {liveWorkspaces.length === 1 ? '' : 's'}. Its members appear in
                    the Home Feed in priority order.
                  </p>
                </div>
              </div>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
                <div className="flex size-12 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500">
                  <Folder className="size-5" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">
                    {project?.name} has no workspaces yet
                  </p>
                  <p className="mt-1 max-w-sm text-sm leading-relaxed text-muted-foreground">
                    Open any workspace and use its “Add to project” action to move it
                    here, or create a new workspace.
                  </p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  className="cursor-pointer rounded-md bg-[#FEA853] text-black hover:bg-[#FEA853]"
                  onClick={() => navigate('/new')}
                >
                  <Plus className="size-4" />
                  New workspace
                </Button>
              </div>
            )}
          </main>
        </div>
      )}

      {/* Rename dialog */}
      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename project</DialogTitle>
            <DialogDescription>Names are saved in Title Case.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 p-4 pt-0">
            <Label htmlFor="project-hub-rename">Project name</Label>
            <Input
              id="project-hub-rename"
              value={draftName}
              maxLength={100}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void handleRename()
              }}
              autoFocus
            />
            {dialogError && <p className="text-xs text-destructive">{dialogError}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              className="bg-[#FEA853] text-black hover:bg-[#FEA853]"
              onClick={() => void handleRename()}
              disabled={busy || !draftName.trim()}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Archive dialog */}
      <Dialog open={archiveOpen} onOpenChange={(open) => !open && setArchiveOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive project?</DialogTitle>
            <DialogDescription>
              {project && memberCount > 0 ? (
                <>
                  “{project.name}” will move to the archive along with its{' '}
                  {memberCount} workspace{memberCount === 1 ? '' : 's'}. You can restore
                  it and everything in it from the Archive page.
                </>
              ) : (
                <>
                  “{project?.name}” will move to the archive. You can restore it from
                  the Archive page.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {dialogError && <p className="px-4 text-xs text-destructive">{dialogError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setArchiveOpen(false)} disabled={busy}>
              Cancel
            </Button>
            <Button
              className="bg-[#FEA853] text-black hover:bg-[#FEA853] cursor-pointer"
              onClick={() => void handleArchive()}
              disabled={busy}
            >
              Archive
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete dialog */}
      <Dialog open={deleteOpen} onOpenChange={(open) => !open && setDeleteOpen(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete project?</DialogTitle>
            <DialogDescription>
              {project &&
              project.workspace_count + project.archived_workspace_count > 0 ? (
                <>
                  “{project.name}” still contains{' '}
                  {project.workspace_count + project.archived_workspace_count} workspace
                  {project.workspace_count + project.archived_workspace_count === 1
                    ? ''
                    : 's'}
                  . A project must be emptied (workspaces deleted, unlinked, or
                  restored) before it can be deleted.
                </>
              ) : (
                <>
                  “{project?.name}” will be permanently removed. This can't be
                  undone.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {dialogError && <p className="px-4 text-xs text-destructive">{dialogError}</p>}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button variant="destructive" onClick={() => void handleDelete()} disabled={busy}>
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function WorkspaceRailItem({
  workspace,
  selected,
  onOpen,
}: {
  workspace: ProjectDetailDto['workspaces'][number]
  selected: boolean
  onOpen: () => void
}) {
  const specialists = useWorkspaceSpecialists(workspace.id)
  return (
    <button
      type="button"
      onClick={onOpen}
      className={cn(
        'flex w-full cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-left transition-colors',
        selected
          ? 'bg-amber-500/10 text-amber-500'
          : 'hover:bg-muted/70 hover:text-foreground',
      )}
    >
      {specialists.length > 0 ? (
        <div className="relative ml-0.5">
          <SpecialistAvatarGroup specialists={specialists} />
        </div>
      ) : (
        <div className="flex size-8 shrink-0 items-center justify-center rounded-full border border-primary/10 bg-muted text-[11px] font-medium text-muted-foreground">
          {(workspaceDisplayName(workspace)[0] ?? '?').toUpperCase()}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className={cn('flex items-center gap-1 truncate text-sm font-medium', selected ? 'text-amber-500' : 'text-foreground')}>
          <span className="truncate">{workspaceDisplayName(workspace)}</span>
          {workspace.pinned && <Pin className="size-3 shrink-0 text-muted-foreground" />}
        </p>
        {workspace.product_name && (
          <p className="truncate text-xs text-muted-foreground">{workspace.product_name}</p>
        )}
      </div>
      <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
    </button>
  )
}

export default ProjectHub