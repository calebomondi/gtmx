import { useCallback, useEffect, useState } from "react"
import { toast } from "sonner"

import {
  approveLaceMember, changeLaceRole, inviteLaceMember, leaveLace, listLaceMembers, removeLaceMember,
  type LacePersonDto,
} from "@/lib/api"

export interface LacePeople {
  /** Everyone on the Lace, open invites and requests; null until loaded. */
  people: LacePersonDto[] | null
  error: string | null
  /** Invite by email; the error to show in the form, or null when sent. */
  invite: (email: string, role: "admin" | "member") => Promise<string | null>
  setRole: (userId: string, role: "admin" | "member") => Promise<void>
  remove: (userId: string) => Promise<void>
  approve: (userId: string) => Promise<void>
  leave: () => Promise<boolean>
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

/** A Lace's people, and the changes the person looking may make to them
 * (the server decides who may do what). */
export function useLacePeople(laceId: string): LacePeople {
  const [people, setPeople] = useState<LacePersonDto[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setPeople(await listLaceMembers(laceId))
      setError(null)
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  useEffect(() => void load(), [load])

  // One change, then the list as it stands; failures said in a toast.
  const change = useCallback(async (what: string, run: () => Promise<unknown>) => {
    try {
      await run()
    } catch (err) {
      toast.error(`Couldn't ${what}`, { description: message(err) })
    }
    await load()
  }, [load])

  const invite = useCallback(async (email: string, role: "admin" | "member") => {
    try {
      await inviteLaceMember(laceId, email, role)
    } catch (err) {
      return message(err)
    }
    await load()
    return null
  }, [laceId, load])

  return {
    people, error, invite,
    setRole: (userId, role) => change("change their role", () => changeLaceRole(laceId, userId, role)),
    remove: (userId) => change("remove them", () => removeLaceMember(laceId, userId)),
    approve: (userId) => change("let them in", () => approveLaceMember(laceId, userId)),
    leave: async () => {
      try {
        await leaveLace(laceId)
        return true
      } catch (err) {
        toast.error("Couldn't leave", { description: message(err) })
        return false
      }
    },
  }
}
