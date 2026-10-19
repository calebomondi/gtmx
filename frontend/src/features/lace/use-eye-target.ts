import { useEffect, useState, type RefObject } from "react"

export interface EyeOffset {
  x: number
  y: number
}

// How far the eyes turn, in mascot viewBox units, at full reach.
const MAX_LOOK_X = 8
const MAX_LOOK_Y = 6
// Distance in px from the mascot at which the eyes reach full turn.
const FULL_LOOK_PX = 240
// Where the eyes rest on a field being typed in: past the text typed so far,
// at roughly an average character's width, kept inside the field.
const FIELD_PAD_PX = 12
const CHAR_PX = 7.5

interface Point {
  x: number
  y: number
}

function center(rect: DOMRect): Point {
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 }
}

/** The point on a text field the eyes follow: the end of what is typed. */
function caretPoint(field: HTMLInputElement | HTMLTextAreaElement): Point {
  const rect = field.getBoundingClientRect()
  const reach = Math.min(FIELD_PAD_PX + field.value.length * CHAR_PX, rect.width - FIELD_PAD_PX)
  return { x: rect.left + reach, y: rect.top + rect.height / 2 }
}

function offsetToward(from: Point, to: Point): EyeOffset {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const distance = Math.hypot(dx, dy)
  if (distance < 1) return { x: 0, y: 0 }
  const reach = Math.min(distance / FULL_LOOK_PX, 1)
  return { x: (dx / distance) * reach * MAX_LOOK_X, y: (dy / distance) * reach * MAX_LOOK_Y }
}

/** Where a mascot's eyes look: at the end of the text being typed in a field
 * inside `fields`, otherwise at the pointer, back to centre when it leaves
 * the window. Null (eyes left to the mascot's own animation) when the user
 * prefers reduced motion. */
export function useEyeTarget(mascot: RefObject<Element | null>, fields: RefObject<Element | null>): EyeOffset | null {
  const [look, setLook] = useState<EyeOffset | null>(null)

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return
    let pointer: Point | null = null
    let frame = 0

    const update = () => {
      frame = 0
      const face = mascot.current?.getBoundingClientRect()
      if (!face) return
      const active = document.activeElement
      const typing = (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement)
        && fields.current?.contains(active)
      const target = typing ? caretPoint(active) : pointer
      setLook(target ? offsetToward(center(face), target) : { x: 0, y: 0 })
    }
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }
    const onMove = (event: PointerEvent) => {
      pointer = { x: event.clientX, y: event.clientY }
      schedule()
    }
    const onLeave = (event: MouseEvent) => {
      if (event.relatedTarget) return
      pointer = null
      schedule()
    }

    window.addEventListener("pointermove", onMove)
    document.addEventListener("mouseout", onLeave)
    document.addEventListener("focusin", schedule)
    document.addEventListener("focusout", schedule)
    document.addEventListener("input", schedule)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener("pointermove", onMove)
      document.removeEventListener("mouseout", onLeave)
      document.removeEventListener("focusin", schedule)
      document.removeEventListener("focusout", schedule)
      document.removeEventListener("input", schedule)
    }
  }, [mascot, fields])

  return look
}
