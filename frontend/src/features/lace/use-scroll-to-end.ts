import { useLayoutEffect, useRef } from "react"

/** A scroll box that starts at its newest content: at the bottom when it
 * opens on something new (`key`) and whenever more arrives (`count`). */
export function useScrollToEnd<T extends HTMLElement>(key: string, count: number) {
  const ref = useRef<T>(null)
  useLayoutEffect(() => {
    const box = ref.current
    if (box) box.scrollTop = box.scrollHeight
  }, [key, count])
  return ref
}
