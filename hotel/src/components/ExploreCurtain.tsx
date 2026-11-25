import { useEffect, useRef } from "react"
import { cn } from "@/lib/cn"

type Props = {
  open: boolean
  onChange: (open: boolean) => void
  onReserve: () => void
}

const links = [
  { label: "The House", href: "#top" },
  { label: "The Table", href: "#table" },
  { label: "The Rooms", href: "#rooms" },
  { label: "Contact", href: "#contact" },
]

/**
 * The Kinetic Menu: a vertical EXPLORE word on the right edge that drops a
 * full-screen obsidian curtain instead of a hamburger drawer.
 */
export function ExploreCurtain({ open, onChange, onReserve }: Props) {
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    closeRef.current?.focus()

    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onChange(false)
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener("keydown", onKey)
    }
  }, [open, onChange])

  const goTo = (href: string) => {
    onChange(false)
    const id = href.replace("#", "")
    window.setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" })
    }, 80)
  }

  return (
    <>
      <button
        type="button"
        onClick={() => onChange(true)}
        aria-expanded={open}
        className={cn(
          "label fixed right-[calc(2vw+0.7rem)] top-1/2 z-50 -translate-y-1/2 text-obsidian/60 transition-all duration-500 hover:text-umber",
          open && "pointer-events-none opacity-0",
        )}
        style={{ writingMode: "vertical-rl" }}
      >
        Explore
      </button>

      <div
        aria-hidden={!open}
        inert={!open}
        className={cn(
          "fixed inset-0 z-[70] flex flex-col justify-between bg-obsidian px-[7vw] py-[9vh] text-parchment transition-[clip-path] duration-[900ms] ease-[cubic-bezier(0.76,0,0.24,1)]",
          open ? "pointer-events-auto" : "pointer-events-none",
        )}
        style={{ clipPath: open ? "inset(0% 0% 0% 0%)" : "inset(0% 0% 100% 0%)" }}
      >
        <div className="flex items-start justify-between gap-6">
          <p className="label text-parchment/45">
            Derfed
            <br />
            Delicasies
          </p>
          <button
            ref={closeRef}
            type="button"
            onClick={() => onChange(false)}
            className="label text-parchment/60 transition-colors hover:text-parchment"
          >
            Close
          </button>
        </div>

        <nav aria-label="Sections" className="flex flex-col gap-2 md:gap-3">
          {links.map((link, index) => (
            <button
              key={link.href}
              type="button"
              onClick={() => goTo(link.href)}
              className="group flex items-baseline gap-5 text-left"
            >
              <span className="label w-8 text-parchment/35">{String(index + 1).padStart(2, "0")}</span>
              <span className="display text-[clamp(2rem,6.5vw,4.8rem)] transition-colors duration-300 group-hover:text-umber">
                {link.label}
              </span>
            </button>
          ))}
        </nav>

        <div className="flex flex-wrap items-end justify-between gap-4 border-t border-parchment/20 pt-6">
          <button
            type="button"
            onClick={() => {
              onChange(false)
              window.setTimeout(onReserve, 80)
            }}
            className="label rounded-full bg-parchment px-6 py-3 text-obsidian transition-colors hover:bg-umber hover:text-parchment"
          >
            Reserve a room
          </button>
          <p className="label text-parchment/40">2°16′S 40°54′E</p>
        </div>
      </div>
    </>
  )
}
