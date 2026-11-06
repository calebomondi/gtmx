import { useEffect, useRef, type ReactNode } from 'react'

/** The details step in a modal window of its own. The hero's scroll scene
 * would otherwise take the page's scroll and hide a form taller than the
 * screen, so the page behind is held still while it's open, and the window
 * scrolls instead. Escape and ✕ mean "skip", like the form's own link. */
export function DetailsDialog({ onSkip, children }: { onSkip: () => void; children: ReactNode }) {
  const dialog = useRef<HTMLDialogElement>(null)

  useEffect(() => {
    const el = dialog.current
    if (!el) return
    el.showModal()
    const root = document.documentElement
    const overflow = root.style.overflow
    root.style.overflow = 'hidden'
    return () => {
      root.style.overflow = overflow
      el.close()
    }
  }, [])

  return (
    <dialog
      ref={dialog}
      aria-label="Tell us about your startup"
      onCancel={(e) => {
        // Closing is the parent's to do, once the skip has gone through.
        e.preventDefault()
        onSkip()
      }}
      className="fixed inset-0 m-auto h-fit max-h-[calc(100dvh-2rem)] w-[min(40rem,calc(100vw-2rem))] overflow-y-auto overscroll-contain rounded-2xl bg-paper p-5 text-ink shadow-lift backdrop:bg-ink/50 backdrop:backdrop-blur-sm sm:p-7"
    >
      <button
        type="button"
        onClick={onSkip}
        aria-label="Close"
        className="absolute top-3 right-3 grid size-9 cursor-pointer place-items-center rounded-full text-muted transition hover:bg-ink/5 hover:text-ink"
      >
        <svg aria-hidden viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M6 6l12 12M18 6L6 18" />
        </svg>
      </button>
      {children}
    </dialog>
  )
}
