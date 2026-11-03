import { useEffect, useState, type RefObject } from 'react'

import { prefersStill } from './motion'

/** How far Lace's eyes turn towards the pointer, in its viewBox units. */
const LOOK_REACH = 8
/** Beyond this distance from Lace, its eyes turn all the way. */
const LOOK_FULL_PX = 320

/** Where Lace (in `el`) looks: towards the mouse, turning further the further
 * away it is; straight ahead without a mouse or with reduced motion. */
export function useLookAtPointer(el: RefObject<HTMLElement | null>): { x: number; y: number } | null {
  const [look, setLook] = useState<{ x: number; y: number } | null>(null)
  useEffect(() => {
    if (prefersStill()) return
    let frame = 0
    const onMove = (event: PointerEvent) => {
      if (event.pointerType !== 'mouse' || frame) return
      frame = requestAnimationFrame(() => {
        frame = 0
        const box = el.current?.getBoundingClientRect()
        if (!box) return
        const dx = event.clientX - (box.left + box.width / 2)
        const dy = event.clientY - (box.top + box.height / 2)
        const dist = Math.hypot(dx, dy) || 1
        const reach = LOOK_REACH * Math.min(1, dist / LOOK_FULL_PX)
        setLook({ x: (dx / dist) * reach, y: (dy / dist) * reach })
      })
    }
    window.addEventListener('pointermove', onMove)
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(frame)
    }
  }, [el])
  return look
}
