import { useEffect, useMemo, useState } from 'react'
import { Check, FolderPlus, MinusCircle, Search } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { workspaceDisplayName } from '@/lib/api'
import type { WorkspaceSummary } from '@/lib/api'
import {
  addToProject,
  removeFromProject,
} from '@/lib/workspaces-store'
import {
  ensureProjectsLoaded,
  refetchProjects,
  useProjects,
} from '@/lib/projects-store'

const displayName = (workspace: WorkspaceSummary) =>
  workspaceDisplayName(workspace)

/**
 * "Add to project" surface for a workspace. Shows the user's projects grouped
 * into Priority / Other buckets with a search bar on top; clicking a project
 * assigns the workspace to it in one action.
 */
export function ProjectPicker({
  workspace,
  open,
  onOpenChange,
}: {
  workspace: WorkspaceSummary
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { projects } = useProjects()
  const [query, setQuery] = useState('')
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    if (open) {
      ensureProjectsLoaded()
      setQuery('')
    }
    // Refresh on every open so a project created elsewhere shows up.
    if (open && projects.length === 0) void refetchProjects().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    const matches = (name: string) => !q || name.toLowerCase().includes(q)
    const priority = projects.filter((p) => p.priority && matches(p.name))
    const other = projects.filter((p) => !p.priority && matches(p.name))
    return { priority, other }
  }, [projects, query])

  const inProject = projects.find((p) => p.id === workspace.project_id) ?? null

  const handlePick = async (projectId: string) => {
    setBusy(projectId)
    try {
      await addToProject(workspace.id, projectId)
      const project = projects.find((p) => p.id === projectId)
      // Membership changed, so the projects' workspace_count badges are stale.
      void refetchProjects()
      toast.success(`Added to ${project?.name ?? 'project'}`)
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const handleRemove = async () => {
    setBusy('remove')
    try {
      await removeFromProject(workspace.id)
      void refetchProjects()
      toast.success('Removed from project')
      onOpenChange(false)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  const renderRow = (project: (typeof projects)[number]) => {
    const isMember = workspace.project_id === project.id
    return (
      <button
        key={project.id}
        type="button"
        disabled={busy !== null}
        onClick={() => {
          if (!isMember) void handlePick(project.id)
        }}
        aria-pressed={isMember}
        className={cn(
          'group flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent',
          isMember && 'cursor-default text-muted-foreground hover:bg-transparent',
        )}
      >
        <span className="min-w-0 flex-1 truncate font-medium">{project.name}</span>
        <span className="shrink-0 text-xs text-muted-foreground">
          {project.workspace_count} workspace{project.workspace_count === 1 ? '' : 's'}
        </span>
        {isMember ? (
          <Check className="size-4 shrink-0 text-amber-500" />
        ) : (
          <FolderPlus className="size-4 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        )}
      </button>
    )
  }

  const hasProjects = filtered.priority.length + filtered.other.length

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{inProject ? "Change project" : "Add to project"}</DialogTitle>
          <DialogDescription>
            {inProject ? (
              <>
                Move “{displayName(workspace)}” to a different project, or take it out
                of the one it's in.
              </>
            ) : (
              <>
                Choose a project for “{displayName(workspace)}”. Projects group
                workspaces from the same company.
              </>
            )}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 p-4 pt-0">
          {inProject && (
            <div className="flex items-center justify-between gap-2 rounded-md border border-primary/15 bg-muted/50 px-3 py-2 text-sm">
              <span className="min-w-0 truncate">
                Currently in <span className="font-medium">{inProject.name}</span>
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="shrink-0"
                disabled={busy !== null}
                onClick={() => void handleRemove()}
              >
                <MinusCircle className="size-3.5" />
                Remove
              </Button>
            </div>
          )}

          <div className="relative">
            <Search className="absolute top-1/2 left-2.5 size-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search projects…"
              className="h-9 bg-muted/60 pl-8 text-sm"
              aria-label="Search projects"
            />
          </div>

          <div className="max-h-72 overflow-y-auto">
            {hasProjects === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {query.trim()
                  ? 'No projects match your search.'
                  : 'No projects yet. Create one from the Projects page.'}
              </p>
            ) : (
              <div className="grid gap-3">
                {filtered.priority.length > 0 && (
                  <ProjectSection label="Priority Workspaces" count={filtered.priority.length}>
                    {filtered.priority.map((project) => renderRow(project))}
                  </ProjectSection>
                )}
                {filtered.other.length > 0 && (
                  <ProjectSection label="Other Workspaces" count={filtered.other.length}>
                    {filtered.other.map((project) => renderRow(project))}
                  </ProjectSection>
                )}
              </div>
            )}
          </div>
        </div>

        <DialogFooter className="gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function ProjectSection({
  label,
  count,
  children,
}: {
  label: string
  count: number
  children: React.ReactNode
}) {
  return (
    <div>
      <p className="mb-1 flex items-baseline justify-between px-2 text-[11px] font-medium tracking-wide text-muted-foreground uppercase">
        <span>{label}</span>
        <span>{count}</span>
      </p>
      <div>{children}</div>
    </div>
  )
}