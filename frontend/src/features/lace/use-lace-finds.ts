import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import {
  approveFind, editMyFind, listFindReviews, listMyFinds, pushFinds, removeMyFind, sendBackFind,
  type FindDto, type FindEdit, type FindKind,
} from "@/lib/api"

/** How each kind of find is named on its own, matching the Feed's tabs. */
export const FIND_KIND_LABEL: Record<FindKind, string> = {
  competitor: "Competitor", account: "Lead", opportunity: "Opportunity",
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** A list of finds, loaded again whenever `key` changes (a turn ended, new
 * activity came in); null until the first load, and while `enabled` is off. */
function useFindList(load: () => Promise<FindDto[]>, enabled: boolean, key: string) {
  const [items, setItems] = useState<FindDto[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  // Bumped to load again after a change.
  const [version, setVersion] = useState(0)
  useEffect(() => {
    if (!enabled) return
    let current = true  // a slower, older load never overwrites a newer one
    load().then((next) => {
      if (current) {
        setItems(next)
        setError(null)
      }
    }, (err: unknown) => current && setError(message(err)))
    return () => {
      current = false
    }
  }, [enabled, key, load, version])
  const reload = useCallback(() => setVersion((v) => v + 1), [])
  return { items, error, reload }
}

/** One change, then the list as it stands; a failure is said in a toast. */
async function change(what: string, run: () => Promise<unknown>, reload: () => void): Promise<boolean> {
  try {
    await run()
    return true
  } catch (err) {
    toast.error(`Couldn't ${what}`, { description: message(err) })
    return false
  } finally {
    reload()
  }
}

export interface MyFinds {
  items: FindDto[] | null
  error: string | null
  /** Put these up for the team's review. */
  push: (finds: FindDto[]) => Promise<void>
  /** Rename, reword or note one; whether it saved. */
  edit: (find: FindDto, changes: FindEdit) => Promise<boolean>
  remove: (find: FindDto) => Promise<void>
}

/** What the founder's private chat found, and pushing it to the team. */
export function useMyFinds(laceId: string, enabled: boolean, key: string): MyFinds {
  const load = useCallback(() => listMyFinds(laceId), [laceId])
  const { items, error, reload } = useFindList(load, enabled, key)
  const push = useCallback(async (finds: FindDto[]) => {
    if (await change("push them to the team", () => pushFinds(laceId, finds), reload)) {
      toast.success(`Sent ${finds.length === 1 ? finds[0].name : `${finds.length} finds`} to the team for review`)
    }
  }, [laceId, reload])
  const edit = useCallback((find: FindDto, changes: FindEdit) =>
    change(`change ${find.name}`, () => editMyFind(laceId, find, changes), reload), [laceId, reload])
  const remove = useCallback(async (find: FindDto) => {
    if (await change(`remove ${find.name}`, () => removeMyFind(laceId, find), reload)) {
      toast.success(`Removed ${find.name}`, { description: "Your chat won't suggest it again." })
    }
  }, [laceId, reload])
  return { items, error, push, edit, remove }
}

export interface FindReviews {
  items: FindDto[] | null
  error: string | null
  approve: (find: FindDto) => Promise<void>
  sendBack: (find: FindDto, note: string) => Promise<void>
}

/** Finds teammates pushed to the team, and deciding them. */
export function useFindReviews(laceId: string, key: string): FindReviews {
  const load = useCallback(() => listFindReviews(laceId), [laceId])
  const { items, error, reload } = useFindList(load, true, key)
  const approve = useCallback(async (find: FindDto) => {
    await change(`approve ${find.name}`, () => approveFind(laceId, find), reload)
  }, [laceId, reload])
  const sendBack = useCallback(async (find: FindDto, note: string) => {
    await change(`send ${find.name} back`, () => sendBackFind(laceId, find, note), reload)
  }, [laceId, reload])
  return { items, error, approve, sendBack }
}
