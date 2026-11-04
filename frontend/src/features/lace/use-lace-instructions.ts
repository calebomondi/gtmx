import { useCallback, useEffect, useState } from "react"

import {
  addLaceInstruction, deleteLaceInstruction, editLaceInstruction, listLaceInstructions,
  type InstructionScope, type LaceInstructionDto,
} from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceInstructions {
  /** Null while loading. */
  items: LaceInstructionDto[] | null
  error: string | null
  /** The id being changed, "new" while one is added; null when idle. */
  busy: string | null
  add: (text: string, appliesTo: InstructionScope) => Promise<boolean>
  edit: (id: string, text: string, appliesTo: InstructionScope) => Promise<boolean>
  remove: (id: string) => Promise<void>
}

/** A Lace's standing instructions, oldest first, with the team's changes to them. */
export function useLaceInstructions(laceId: string): LaceInstructions {
  const [items, setItems] = useState<LaceInstructionDto[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    listLaceInstructions(laceId)
      .then((next) => !cancelled && setItems(next))
      .catch((err) => !cancelled && setError(message(err)))
    return () => { cancelled = true }
  }, [laceId])

  const run = useCallback(async (key: string, change: () => Promise<void>): Promise<boolean> => {
    setBusy(key)
    setError(null)
    try {
      await change()
      return true
    } catch (err) {
      setError(message(err))
      return false
    } finally {
      setBusy(null)
    }
  }, [])

  const add = useCallback((text: string, appliesTo: InstructionScope) => run("new", async () => {
    const made = await addLaceInstruction(laceId, text, appliesTo)
    setItems((prev) => [...(prev ?? []), made])
  }), [laceId, run])

  const edit = useCallback((id: string, text: string, appliesTo: InstructionScope) => run(id, async () => {
    const changed = await editLaceInstruction(laceId, id, text, appliesTo)
    setItems((prev) => prev?.map((i) => (i.id === id ? changed : i)) ?? null)
  }), [laceId, run])

  const remove = useCallback(async (id: string) => {
    await run(id, async () => {
      await deleteLaceInstruction(laceId, id)
      setItems((prev) => prev?.filter((i) => i.id !== id) ?? null)
    })
  }, [laceId, run])

  return { items, error, busy, add, edit, remove }
}
