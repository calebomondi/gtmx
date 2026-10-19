import { useState, type ReactNode } from "react"
import { useNavigate } from "react-router-dom"
import { BookOpen, Building2, Home, Link2, MessagesSquare, Sparkles, SquarePen, Swords, User } from "lucide-react"

import { Lace } from "@/components/lace-mascot"
import {
  Command,
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command"
import type { LaceSearchHitDto, LaceSearchKind } from "@/lib/api"
import { useLaces } from "@/lib/laces-store"

import { hitPath, SEARCH_KIND_LABELS } from "./search-paths"
import { useLaceSearch } from "./use-lace-search"

const MASCOT_PX = 16

const KIND_ICONS: Record<Exclude<LaceSearchKind, "lace">, ReactNode> = {
  fact: <BookOpen />,
  competitor: <Swords />,
  account: <Building2 />,
  contact: <User />,
  opportunity: <Sparkles />,
  conversation: <MessagesSquare />,
}

const QUICK_ACTIONS = [
  { label: "New Lace", path: "/new", icon: <SquarePen /> },
  { label: "Home", path: "/feed", icon: <Home /> },
  { label: "Connected accounts", path: "/accounts", icon: <Link2 /> },
]

function HitItem({ hit, onSelect }: { hit: LaceSearchHitDto; onSelect: (path: string) => void }) {
  return (
    <CommandItem value={`${hit.kind}:${hit.id}`} onSelect={() => onSelect(hitPath(hit))}>
      {hit.kind === "lace" ? <Lace state="idle" size={MASCOT_PX} animated={false} decorative /> : KIND_ICONS[hit.kind]}
      <div className="flex min-w-0 flex-1 flex-col">
        <span className="truncate">{hit.title}</span>
        {hit.subtitle && <span className="truncate text-xs text-muted-foreground">{hit.subtitle}</span>}
      </div>
      {hit.kind !== "lace" && <span className="shrink-0 text-xs text-muted-foreground">{hit.lace_name}</span>}
    </CommandItem>
  )
}

function DefaultView({ onSelect }: { onSelect: (path: string) => void }) {
  const { laces } = useLaces()
  return (
    <>
      {laces.length > 0 && (
        <CommandGroup heading="Your Laces">
          {laces.map((lace) => (
            <CommandItem key={lace.id} value={`lace:${lace.id}`} onSelect={() => onSelect(`/lace/${lace.id}`)}>
              <Lace state="idle" size={MASCOT_PX} animated={false} decorative />
              <span className="truncate">{lace.name}</span>
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

/** Search across every Lace: what each knows, its competitors, accounts,
 * contacts, opportunities and conversations. Empty, it lists the Laces. */
export function LaceSearch({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const navigate = useNavigate()
  const [query, setQuery] = useState("")
  const search = useLaceSearch(query)

  const close = (next: boolean) => {
    if (!next) setQuery("")
    onOpenChange(next)
  }
  const go = (path: string) => {
    close(false)
    navigate(path)
  }

  return (
    <CommandDialog open={open} onOpenChange={close} title="Search"
                   description="Search your Laces: what they know, competitors, accounts, contacts, opportunities and conversations">
      <Command shouldFilter={false}>
        <CommandInput placeholder="Search your Laces…" value={query} onValueChange={setQuery} />
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
                <CommandGroup key={kind} heading={SEARCH_KIND_LABELS[kind]}>
                  {hits.map((hit) => <HitItem key={`${hit.kind}:${hit.id}`} hit={hit} onSelect={go} />)}
                </CommandGroup>
              ))}
            </>
          )}
        </CommandList>
      </Command>
    </CommandDialog>
  )
}
