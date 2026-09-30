import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  ChevronDown,
  PinIcon,
  PinOffIcon,
  PencilIcon,
  Trash2Icon,
  FolderPlus,
  Archive,
} from "lucide-react"

import {
  renameWorkspace,
  removeWorkspace,
  toggleWorkspacePin,
  archiveWorkspaceAction,
} from "@/lib/workspaces-store"
import {
  workspaceDisplayName,
  type WorkspaceSummary,
} from "@/lib/api"
import { ProjectPicker } from "@/components/project-picker"

const MAX_NAME_LENGTH = 100

/**
 * Header control for a real workspace: shows the workspace label and offers
 * rename / pin / delete. Replaces the sample TeamSwitcher on `/workspace/:id`.
 */
export function WorkspaceManager({
  workspace,
}: {
  workspace: WorkspaceSummary
}) {
  const navigate = useNavigate()
  const [renameOpen, setRenameOpen] = useState(false)
  const [deleteOpen, setDeleteOpen] = useState(false)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [draftName, setDraftName] = useState(workspaceDisplayName(workspace))
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const displayName = workspaceDisplayName(workspace)

  const handleRename = async () => {
    const name = draftName.trim()
    if (!name || name.length > MAX_NAME_LENGTH) {
      setError(
        name.length > MAX_NAME_LENGTH
          ? `Name must be ${MAX_NAME_LENGTH} characters or fewer.`
          : "Name cannot be empty.",
      )
      return
    }
    setBusy(true)
    setError(null)
    try {
      await renameWorkspace(workspace.id, name)
      setRenameOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleTogglePin = async () => {
    setError(null)
    try {
      await toggleWorkspacePin(workspace.id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const handleDelete = async () => {
    setBusy(true)
    setError(null)
    try {
      await removeWorkspace(workspace.id)
      setDeleteOpen(false)
      navigate("/feed", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const handleArchive = async () => {
    setBusy(true)
    setError(null)
    try {
      await archiveWorkspaceAction(workspace.id)
      navigate("/archive", { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-w-0 items-center gap-2">
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              className="h-8 min-w-0 max-w-72 gap-1.5 px-2 text-sm font-medium"
            />
          }
        >
          <span className="truncate">{displayName}</span>
          <ChevronDown className="size-3.5 shrink-0" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" sideOffset={6}>
          <DropdownMenuItem
            className="gap-2"
            onClick={() => {
              setDraftName(displayName)
              setError(null)
              setRenameOpen(true)
            }}
          >
            <PencilIcon className="size-4" />
            Rename
          </DropdownMenuItem>
          <DropdownMenuItem className="gap-2" onClick={() => void handleTogglePin()}>
            {workspace.pinned ? (
              <PinOffIcon className="size-4" />
            ) : (
              <PinIcon className="size-4" />
            )}
            {workspace.pinned ? "Unpin" : "Pin"}
          </DropdownMenuItem>
          <DropdownMenuItem
            className="gap-2"
            onClick={() => {
              setError(null)
              setPickerOpen(true)
            }}
          >
            <FolderPlus className="size-4" />
            Add to project
          </DropdownMenuItem>
          <DropdownMenuItem
            className="gap-2"
            disabled={busy}
            onClick={() => void handleArchive()}
          >
            <Archive className="size-4" />
            Archive
          </DropdownMenuItem>
          <DropdownMenuItem
            className="gap-2 text-destructive focus:text-destructive"
            onClick={() => {
              setError(null)
              setDeleteOpen(true)
            }}
          >
            <Trash2Icon className="size-4" />
            Delete
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {error && (
        <span className="max-w-56 truncate text-xs text-destructive">{error}</span>
      )}

      <Dialog open={renameOpen} onOpenChange={setRenameOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename workspace</DialogTitle>
            <DialogDescription>
              This is your label for the workspace — the product/service name the agent
              found stays as-is.
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-2 p-4 pt-0">
            <Label htmlFor="workspace-rename">Name</Label>
            <Input
              id="workspace-rename"
              value={draftName}
              maxLength={MAX_NAME_LENGTH}
              onChange={(event) => setDraftName(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") void handleRename()
              }}
              autoFocus
            />
            {error && <p className="text-xs text-destructive">{error}</p>}
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRenameOpen(false)}
              disabled={busy}
            >
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

      <Dialog open={deleteOpen} onOpenChange={setDeleteOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete workspace?</DialogTitle>
            <DialogDescription>
              "{displayName}" and everything stored in it will be removed. This
              can't be undone.
            </DialogDescription>
          </DialogHeader>
          {error && (
            <p className="px-4 text-xs text-destructive">{error}</p>
          )}
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteOpen(false)}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleDelete()}
              disabled={busy}
            >
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <ProjectPicker
        workspace={workspace}
        open={pickerOpen}
        onOpenChange={setPickerOpen}
      />
    </div>
  )
}
