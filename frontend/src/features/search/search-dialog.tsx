import { useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { Archive, Building2, FolderClosed, Home, LayoutGrid, Link2, Radio, SquarePen, Swords } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import { workspaceDisplayName, type SearchHitDto, type SearchKind } from "@/lib/api"
import { useWorkspaces } from "@/lib/workspaces-store"
import { hitPath, KIND_LABELS } from "./search-paths"
import { useSearch } from "./use-search"

const RECENT_COUNT = 5

const KIND_ICONS: Record<SearchKind, ReactNode> = {
  workspace: <LayoutGrid />,
  project: <FolderClosed />,
  competitor: <Swords />,
  account: <Building2 />,
  signal: <Radio />,
}

const QUICK_ACTIONS = [
  { label: "New Lace", path: "/new", icon: <SquarePen /> },
  { label: "Home feed", path: "/feed", icon: <Home /> },
  { label: "Connected accounts", path: "/accounts", icon: <Link2 /> },
  { label: "Archive", path: "/archive", icon: <Archive /> },
]

function HitItem({ hit, onSelect }: { hit: SearchHitDto; onSelect: (path: string) => void }) {
  return (
    <CommandItem value={`${hit.kind}:${hit.id}`} onSelect={() => onSelect(hitPath(hit))}>
      {KIND_ICONS[hit.kind]}
      <div className="flex min-w-0 flex-col">
        <span className="truncate">{hit.title}</span>
        {hit.subtitle && <span className="truncate text-xs text-muted-foreground">{hit.subtitle}</span>}
      </div>
      <div className="ml-auto flex shrink-0 gap-1">
        {hit.offer_type && <Badge variant="outline" className="capitalize">{hit.offer_type}</Badge>}
        {hit.archived && <Badge variant="secondary">Archived</Badge>}
      </div>
    </CommandItem>
  )
}

function DefaultView({ onSelect }: { onSelect: (path: string) => void }) {
  const recent = useWorkspaces().workspaces.slice(0, RECENT_COUNT)
  return (
    <>
      {recent.length > 0 && (
        <CommandGroup heading="Recent workspaces">
          {recent.map((w) => (
            <CommandItem key={w.id} value={`recent:${w.id}`} onSelect={() => onSelect(`/workspace/${w.id}`)}>
              <LayoutGrid />
              <span className="truncate">{workspaceDisplayName(w)}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      )}
      <CommandGroup heading="Go to">
        {QUICK_ACTIONS.map((a) => (
          <CommandItem key={a.path} value={`go:${a.path}`} onSelect={() => onSelect(a.path)}>
            {a.icon}
            <span>{a.label}</span>
          </CommandItem>
        ))}
      </CommandGroup>
    </>
  )
}

/** Search Anything: the user's workspaces, projects, competitors, accounts
 * and feed, by name. Empty, it offers recent workspaces and shortcuts. */
export function SearchDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState("")
  const search = useSearch(query)

  const close = (next: boolean) => {
    if (!next) setQuery("")
    onOpenChange(next)
  }
  const go = (path: string) => {
    close(false)
    navigate(path)
  }

  return (
    <CommandDialog open={open} onOpenChange={close} title="Search Anything" description="Search your workspaces, projects, competitors, accounts and feed">
      <Command shouldFilter={false}>
        <CommandInput placeholder="Search workspaces, competitors, accounts…" value={query} onValueChange={setQuery} />
        <CommandList>
          {search.idle ? (
            <DefaultView onSelect={go} />
          ) : (
            <>
              {search.error && <p className="px-3 py-6 text-center text-sm text-destructive">{search.error}</p>}
              {!search.error && search.loading && search.groups.length === 0 && (
                <p className="px-3 py-6 text-center text-sm text-muted-foreground">Searching…</p>
              )}
              {!search.error && !search.loading && <CommandEmpty>No matches for “{query.trim()}”.</CommandEmpty>}
              {search.groups.map(([kind, hits]) => (
                <CommandGroup key={kind} heading={KIND_LABELS[kind]}>
                  {hits.map((hit) => (
                    <HitItem key={hit.id} hit={hit} onSelect={go} />
                  ))}
                </CommandGroup>
              ))}
            </>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
