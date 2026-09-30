import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import type { DragEndEvent, UniqueIdentifier } from '@dnd-kit/core'
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { toast } from 'sonner'
import {
  Archive,
  Folder,
  GripVerticalIcon,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
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
import { cn } from '@/lib/utils'
import type { ProjectDto } from '@/lib/api'
import {
  archiveProjectAction,
  createProject,
  deleteProjectAction,
  ensureProjectsLoaded,
  renameProject,
  reorderProjects,
  useProjects,
} from '@/lib/projects-store'

type ColumnId = 'priority' | 'other'

const COLUMN_LABEL: Record<ColumnId, { title: string; hint: string }> = {
  priority: {
    title: 'Priority Workspaces',
    hint: 'Drag a project here to prioritize its workspaces in the Home Feed.',
  },
  other: {
    title: 'Other Workspaces',
    hint: 'Everything else — drag left to prioritize.',
  },
}

/** Total members, live plus already-archived -- what archiving the project takes with it. */
function archiveCount(project: ProjectDto): number {
  return project.workspace_count + project.archived_workspace_count
}

interface ProjectRowProps {
  project: ProjectDto
  onRename: (project: ProjectDto) => void
  onArchive: (project: ProjectDto) => void
  onDelete: (project: ProjectDto) => void
}

function ProjectRow({ project, onRename, onArchive, onDelete }: ProjectRowProps) {
  const navigate = useNavigate()
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: project.id })

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={cn(
        'flex items-center justify-between gap-3 p-3',
        isDragging && 'bg-background z-20 rounded-md shadow-sm',
      )}
    >
      <button
        type="button"
        aria-label={`Drag ${project.name}`}
        className="inline-flex items-center text-muted-foreground hover:text-foreground"
        {...attributes}
        {...listeners}
      >
        <GripVerticalIcon className="size-4 cursor-grab" />
      </button>

      <button
        type="button"
        onClick={() => navigate(`/projects/${project.id}`)}
        className="flex min-w-0 flex-1 cursor-pointer items-center gap-2 text-left"
      >
        <Folder
          className={cn(
            'size-4 shrink-0',
            project.priority ? 'text-amber-500' : 'text-muted-foreground',
          )}
        />
        <span className="truncate text-[15px] sm:text-base">{project.name}</span>
      </button>

      {/* Workspace-count badge (replaces the old avatar slot). */}
      <span className="inline-flex shrink-0 items-center gap-1 rounded-full border border-primary/10 bg-muted/60 px-2 py-0.5 text-[11px] font-medium tabular-nums text-foreground">
        {project.workspace_count}
        <span className="text-muted-foreground">
          workspace{project.workspace_count === 1 ? '' : 's'}
        </span>
      </span>

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
          <DropdownMenuItem onClick={() => onRename(project)}>
            <Pencil className="size-4" />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem onClick={() => onArchive(project)}>
            <Archive className="size-4" />
            Archive
          </DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem
            variant="destructive"
            onClick={() => onDelete(project)}
          >
            <Trash2 className="size-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}

function ProjectColumn({
  id,
  projects,
  onRename,
  onArchive,
  onDelete,
}: {
  id: ColumnId
  projects: ProjectDto[]
  onRename: (project: ProjectDto) => void
  onArchive: (project: ProjectDto) => void
  onDelete: (project: ProjectDto) => void
}) {
  // The column body is itself a drop target so a card can be dropped into an
  // empty bucket, not only onto another card. Rows are nested inside it, so
  // `closestCenter` still prefers a hovered row over the column.
  const { setNodeRef, isOver } = useDroppable({ id })

  return (
    <div>
      <div className="mb-2">
        <h3 className="text-foreground text-xl font-medium">{COLUMN_LABEL[id].title}</h3>
        <p className="text-muted-foreground mt-0.5 text-xs">{COLUMN_LABEL[id].hint}</p>
      </div>
      <SortableContext
        id={id}
        items={projects.map((project) => project.id)}
        strategy={verticalListSortingStrategy}
      >
        <div
          ref={setNodeRef}
          className={cn(
            'min-h-12 rounded-md transition-colors',
            projects.length === 0 && 'border border-dashed',
            isOver && 'bg-amber-500/[0.06] outline-2 outline-amber-500/40',
          )}
        >
          {projects.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              {isOver ? 'Drop here' : 'Nothing here yet.'}
            </p>
          ) : (
            projects.map((project, index) => (
              <div key={project.id} className={cn(index !== projects.length - 1 && 'border-b')}>
                <ProjectRow
                  project={project}
                  onRename={onRename}
                  onArchive={onArchive}
                  onDelete={onDelete}
                />
              </div>
            ))
          )}
        </div>
      </SortableContext>
    </div>
  )
}

export function ProjectsComponent() {
  const { projects } = useProjects()
  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null)
  const [createOpen, setCreateOpen] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [renameTarget, setRenameTarget] = useState<ProjectDto | null>(null)
  const [archiveTarget, setArchiveTarget] = useState<ProjectDto | null>(null)
  const [deleteTarget, setDeleteTarget] = useState<ProjectDto | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    ensureProjectsLoaded()
  }, [])

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  const priorityProjects = projects.filter((p) => p.priority)
  const otherProjects = projects.filter((p) => !p.priority)

  const findContainer = (id: UniqueIdentifier): ColumnId | null => {
    const value = String(id)
    if (value === 'priority' || priorityProjects.some((p) => p.id === value)) return 'priority'
    if (value === 'other' || otherProjects.some((p) => p.id === value)) return 'other'
    return null
  }

  const projectById = (id: UniqueIdentifier) =>
    projects.find((p) => p.id === String(id)) ?? null

  const activeProject = activeId ? projectById(activeId) : null

  /**
   * Index of a drop target in a list. When the card is dropped on the bucket
   * body rather than on a specific card, it lands at the end of the list.
   */
  const orderIndex = (list: ProjectDto[], overId: UniqueIdentifier): number => {
    const index = list.findIndex((p) => p.id === String(overId))
    if (index !== -1) return index
    return Math.max(list.length - 1, 0)
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event
    setActiveId(null)
    if (!over) return

    const activeContainer = findContainer(active.id)
    const overContainer = findContainer(over.id)
    if (!activeContainer || !overContainer) return

    const fromPriority = activeContainer === 'priority'
    const toPriority = overContainer === 'priority'
    const movingAcross = fromPriority !== toPriority
    const source = fromPriority ? priorityProjects : otherProjects
    const sourceIndex = source.findIndex((p) => p.id === active.id)
    if (sourceIndex === -1) return
    const moved = source[sourceIndex]

    let nextPriority: ProjectDto[]
    let nextOther: ProjectDto[]

    if (!movingAcross) {
      // Reorder within the same bucket.
      const overIndex = orderIndex(source, over.id)
      if (overIndex === sourceIndex) return
      const next = arrayMove(source, sourceIndex, overIndex)
      nextPriority = fromPriority ? next : priorityProjects
      nextOther = fromPriority ? otherProjects : next
    } else {
      const sourceWithout = source.filter((p) => p.id !== active.id)
      const target = toPriority ? priorityProjects : otherProjects
      const overIndex = orderIndex(target, over.id)
      const inserted = [...target]
      inserted.splice(overIndex, 0, moved)
      if (toPriority) {
        nextPriority = inserted
        nextOther = sourceWithout
      } else {
        nextPriority = sourceWithout
        nextOther = inserted
      }
    }

    try {
      await reorderProjects(
        nextPriority.map((p) => p.id),
        nextOther.map((p) => p.id),
      )
      if (movingAcross) {
        toast.success(`Moved to ${COLUMN_LABEL[overContainer].title}`, {
          description: moved.name,
        })
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    }
  }

  const handleCreate = async () => {
    const name = draftName.trim()
    if (!name) {
      setError('Project name cannot be empty.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await createProject(name)
      setCreateOpen(false)
      setDraftName('')
      toast.success('Project created')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleRename = async () => {
    if (!renameTarget) return
    const name = draftName.trim()
    if (!name) {
      setError('Project name cannot be empty.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await renameProject(renameTarget.id, name)
      setRenameTarget(null)
      setDraftName('')
      toast.success('Project renamed')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleArchive = async () => {
    if (!archiveTarget) return
    setBusy(true)
    setError(null)
    try {
      await archiveProjectAction(archiveTarget.id)
      setArchiveTarget(null)
      toast.success('Project archived')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    setBusy(true)
    setError(null)
    try {
      await deleteProjectAction(deleteTarget.id)
      setDeleteTarget(null)
      toast.success('Project deleted')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const hasProjects = projects.length > 0

  return (
    <div className="bg-muted flex min-h-0 flex-1 flex-col p-6">
      <div className="mx-auto flex w-full min-h-0 max-w-3xl flex-1 flex-col">
        <div className="mb-5 flex items-start justify-between gap-2">
          <div>
            <h1 className="text-xl font-medium">Projects</h1>
            <p className="text-muted-foreground mt-0.5 text-sm">
              Grouped workspaces — e.g. every product/service from one company.
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            className="cursor-pointer rounded-md bg-[#FEA853] text-black hover:bg-[#FEA853]"
            onClick={() => {
              setError(null)
              setDraftName('')
              setCreateOpen(true)
            }}
          >
            <Plus className="size-4" />
            New Project
          </Button>
        </div>

        {!hasProjects ? (
          <EmptyProjects onCreate={() => setCreateOpen(true)} />
        ) : (
          <Card>
            <CardContent className="pt-6">
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragStart={(event) => setActiveId(event.active.id)}
                onDragEnd={handleDragEnd}
                onDragCancel={() => setActiveId(null)}
              >
                <div className="grid gap-6 md:grid-cols-2">
                  <ProjectColumn
                    id="priority"
                    projects={priorityProjects}
                    onRename={(project) => {
                      setError(null)
                      setDraftName(project.name)
                      setRenameTarget(project)
                    }}
                    onArchive={(project) => {
                      setError(null)
                      setArchiveTarget(project)
                    }}
                    onDelete={(project) => {
                      setError(null)
                      setDeleteTarget(project)
                    }}
                  />
                  <ProjectColumn
                    id="other"
                    projects={otherProjects}
                    onRename={(project) => {
                      setError(null)
                      setDraftName(project.name)
                      setRenameTarget(project)
                    }}
                    onArchive={(project) => {
                      setError(null)
                      setArchiveTarget(project)
                    }}
                    onDelete={(project) => {
                      setError(null)
                      setDeleteTarget(project)
                    }}
                  />
                </div>
                <DragOverlay>
                  {activeProject ? (
                    <div className="bg-background border-border flex items-center justify-between gap-3 rounded-md border p-3">
                      <GripVerticalIcon className="text-muted-foreground size-4" />
                      <p className="text-muted-foreground flex-1 text-base">
                        {activeProject.name}
                      </p>
                      <span className="text-muted-foreground text-xs">
                        {activeProject.workspace_count} workspace
                        {activeProject.workspace_count === 1 ? '' : 's'}
                      </span>
                    </div>
                  ) : null}
                </DragOverlay>
              </DndContext>
            </CardContent>
          </Card>
        )}
      </div>

      {/* New project */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New project</DialogTitle>
            <DialogDescription>
              A project groups workspaces from the same company. Name it after the
              company.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 p-4 pt-0">
            <Label htmlFor="project-name">Project name</Label>
            <Input
              id="project-name"
              value={draftName}
              maxLength={100}
              placeholder="e.g. Acme Corp"
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void handleCreate()
              }}
              autoFocus
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              className="bg-[#FEA853] text-black hover:bg-[#FEA853] cursor-pointer"
              onClick={() => void handleCreate()}
              disabled={busy || !draftName.trim()}
            >
              Create
            </Button>
            <Button variant="outline" onClick={() => setCreateOpen(false)} disabled={busy} className={'cursor-pointer'}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Rename */}
      <Dialog open={renameTarget !== null} onOpenChange={(open) => !open && setRenameTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename project</DialogTitle>
            <DialogDescription>Names are saved in Title Case.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 p-4 pt-0">
            <Label htmlFor="project-rename">Project name</Label>
            <Input
              id="project-rename"
              value={draftName}
              maxLength={100}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') void handleRename()
              }}
              autoFocus
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRenameTarget(null)} disabled={busy}>
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

      {/* Archive */}
      <Dialog
        open={archiveTarget !== null}
        onOpenChange={(open) => !open && setArchiveTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Archive project?</DialogTitle>
            <DialogDescription>
              {archiveTarget && archiveCount(archiveTarget) > 0 ? (
                <>
                  “{archiveTarget.name}” will move to the archive along with its{' '}
                  {archiveCount(archiveTarget)} workspace
                  {archiveCount(archiveTarget) === 1 ? '' : 's'}. You can restore it
                  and everything in it from the Archive page.
                </>
              ) : (
                <>“{archiveTarget?.name}” will move to the archive. You can restore it
                  from the Archive page.</>
              )}
            </DialogDescription>
          </DialogHeader>
          {error && <p className="px-4 text-xs text-destructive">{error}</p>}
          <DialogFooter>
            <Button
              className="bg-[#FEA853] text-black hover:bg-[#FEA853] cursor-pointer"
              onClick={() => void handleArchive()}
              disabled={busy}
            >
              Archive
            </Button>
            <Button variant="outline" onClick={() => setArchiveTarget(null)} disabled={busy}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete */}
      <Dialog open={deleteTarget !== null} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete project?</DialogTitle>
            <DialogDescription>
              {deleteTarget && deleteTarget.workspace_count + deleteTarget.archived_workspace_count > 0 ? (
                <>
                  “{deleteTarget.name}” still contains{' '}
                  {deleteTarget.workspace_count + deleteTarget.archived_workspace_count} workspace
                  {deleteTarget.workspace_count + deleteTarget.archived_workspace_count === 1 ? '' : 's'}.
                  A project must be emptied (workspaces deleted, unlinked, or restored) before it
                  can be deleted.
                </>
              ) : (
                <>
                  “{deleteTarget?.name}” will be permanently removed. This can't be undone.
                </>
              )}
            </DialogDescription>
          </DialogHeader>
          {error && <p className="px-4 text-xs text-destructive">{error}</p>}
          <DialogFooter>
            <Button variant="destructive" onClick={() => void handleDelete()} disabled={busy}>
              Delete
            </Button>
            <Button variant="outline" onClick={() => setDeleteTarget(null)} disabled={busy}>
              Cancel
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

function EmptyProjects({ onCreate }: { onCreate: () => void }) {
  return (
    <Card className="mt-2">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-14 text-center">
        <div className="flex size-12 items-center justify-center rounded-xl bg-amber-500/10 text-amber-500">
          <Folder className="size-6" />
        </div>
        <div>
          <p className="text-sm font-medium">No projects yet</p>
          <p className="text-muted-foreground mt-1 max-w-sm text-sm">
            Group workspaces from the same company into one project, then open it to
            work across all of them.
          </p>
        </div>
        <Button
          type="button"
          size="sm"
          className="cursor-pointer rounded-md bg-[#FEA853] text-black hover:bg-[#FEA853]"
          onClick={onCreate}
        >
          <Plus className="size-4" />
          Create your first project
        </Button>
      </CardContent>
    </Card>
  )
}

export default ProjectsComponent