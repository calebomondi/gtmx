import { useEffect } from "react"
import { Link } from "react-router-dom"
import { Plus } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { refetchLaces, useLaces } from "@/lib/laces-store"
import { cn } from "@/lib/utils"

import { LaceAvatar } from "./lace-avatar"

export default function LaceList() {
  const { laces, loaded, error } = useLaces()
  useEffect(() => void refetchLaces(), [])
  const loading = !loaded && !error
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-8">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-medium">Your Laces</h1>
        <Link to="/new" className={cn(buttonVariants({ size: "sm" }))}>
          <Plus /> New Lace
        </Link>
      </div>
      {loading && <Skeleton className="h-16 w-full" />}
      {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
      {!loading && !error && laces.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No Laces yet. Create one with your startup's website and it will learn what you sell.
        </p>
      )}
      <ul className="flex flex-col gap-2">
        {laces.map((lace) => (
          <li key={lace.id}>
            <Link to={`/lace/${lace.id}`} className="flex items-center gap-3 rounded-lg border p-3 hover:bg-muted">
              <LaceAvatar state={lace.mood ?? "idle"} />
              <div className="min-w-0">
                <p className="truncate font-medium">{lace.name}</p>
                <p className="truncate text-xs text-muted-foreground">{lace.startup_name ?? lace.website}</p>
              </div>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
