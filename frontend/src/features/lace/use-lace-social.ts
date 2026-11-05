import { useCallback, useEffect, useState } from "react"

import {
  listSocialHeard, listSocialPosts, setSocialItemStatus,
  type HeardStatus, type SocialItemDto, type SocialPostDto,
} from "@/lib/api"

function message(err: unknown): string {
  return err instanceof Error ? err.message : String(err)
}

export interface LaceSocial {
  /** Null while loading. */
  posts: SocialPostDto[] | null
  heard: SocialItemDto[] | null
  error: string | null
  setStatus: (itemId: string, status: HeardStatus) => Promise<void>
}

/** The founder's posts and what the Lace's listen kept, loaded while `open`. */
export function useLaceSocial(laceId: string, open: boolean): LaceSocial {
  const [posts, setPosts] = useState<SocialPostDto[] | null>(null)
  const [heard, setHeard] = useState<SocialItemDto[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!open) return
    let cancelled = false
    Promise.all([listSocialPosts(laceId), listSocialHeard(laceId)])
      .then(([p, h]) => {
        if (cancelled) return
        setPosts(p)
        setHeard(h)
      })
      .catch((err) => !cancelled && setError(message(err)))
    return () => { cancelled = true }
  }, [laceId, open])

  const setStatus = useCallback(async (itemId: string, status: HeardStatus) => {
    try {
      const updated = await setSocialItemStatus(laceId, itemId, status)
      setHeard((prev) => prev?.map((i) => (i.id === itemId ? updated : i)) ?? null)
    } catch (err) {
      setError(message(err))
    }
  }, [laceId])

  return { posts, heard, error, setStatus }
}
