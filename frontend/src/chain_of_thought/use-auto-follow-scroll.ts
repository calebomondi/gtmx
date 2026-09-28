import { useCallback, useEffect, useRef, useState } from "react"

export function useAutoFollowScroll() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [showScrollButton, setShowScrollButton] = useState(false)
  const nearBottomRef = useRef(true)

  const updateScrollButton = useCallback(() => {
    const scrollContainer = containerRef.current

    if (!scrollContainer) return

    const remainingScroll = scrollContainer.scrollHeight - scrollContainer.scrollTop - scrollContainer.clientHeight
    const nearBottom = remainingScroll <= 1
    nearBottomRef.current = nearBottom
    setShowScrollButton(!nearBottom)
  }, [])

  useEffect(() => {
    updateScrollButton()
  }, [updateScrollButton])

  const scrollToBottom = useCallback(() => {
    nearBottomRef.current = true
    setShowScrollButton(false)
    containerRef.current?.scrollTo({
      top: containerRef.current.scrollHeight,
      behavior: 'smooth',
    })
  }, [])

  const followIfNear = useCallback(() => {
    if (nearBottomRef.current) {
      containerRef.current?.scrollTo({
        top: containerRef.current.scrollHeight,
        behavior: 'smooth',
      })
    }
  }, [])

  return { containerRef, showScrollButton, updateScrollButton, scrollToBottom, followIfNear }
}