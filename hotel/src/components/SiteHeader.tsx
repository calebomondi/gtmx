import { useEffect, useState } from "react"
import { cn } from "@/lib/cn"

type Props = {
  onReserve: () => void
}

/** A slim bar that only exists once the hero has been left behind. */
export function SiteHeader({ onReserve }: Props) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > window.innerHeight * 0.8)
    onScroll()
    window.addEventListener("scroll", onScroll, { passive: true })
    return () => window.removeEventListener("scroll", onScroll)
  }, [])

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-[45] transition-all duration-700",
        visible ? "translate-y-0 opacity-100" : "pointer-events-none -translate-y-4 opacity-0",
      )}
    >
      <div className="mx-[2vw] mt-[2vw] flex items-center justify-between border-b border-obsidian/15 bg-parchment/75 px-4 py-3 backdrop-blur-xl md:px-6">
        <a href="#top" className="label text-obsidian/70 transition-colors hover:text-obsidian">
          Derfed Delicasies
        </a>
        <div className="flex items-center gap-6">
          <a href="#rooms" className="label hidden text-obsidian/50 transition-colors hover:text-obsidian sm:block">
            The Rooms
          </a>
          <button
            type="button"
            onClick={onReserve}
            className="label rounded-full border border-obsidian/25 px-4 py-2 text-obsidian transition-colors hover:border-umber hover:text-umber"
          >
            Reserve
          </button>
        </div>
      </div>
    </header>
  )
}
