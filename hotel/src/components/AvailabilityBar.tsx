import { useState } from "react"
import { cn } from "@/lib/cn"
import type { Stay } from "@/lib/content"
import { todayISO } from "@/lib/content"

type Props = {
  stay: Stay
  onChange: (stay: Stay) => void
  onReserve: () => void
}

/**
 * A floating availability pill. It stays out of the image until it is hovered,
 * focused, or tapped, then opens to the two dates and the party size.
 */
export function AvailabilityBar({ stay, onChange, onReserve }: Props) {
  const [expanded, setExpanded] = useState(false)
  const today = todayISO()

  return (
    <div className="fixed bottom-3 left-1/2 z-40 w-[calc(100%-1.5rem)] max-w-[24rem] -translate-x-1/2 sm:w-auto sm:max-w-none md:bottom-[3vh]">
      <div className="group mx-auto flex items-center gap-1 rounded-full border border-obsidian/20 bg-parchment/90 p-1.5 shadow-[0_24px_60px_-30px_rgba(45,41,38,0.65)] backdrop-blur-xl">
        <button
          type="button"
          onClick={() => setExpanded(true)}
          aria-expanded={expanded}
          aria-label="Show availability fields"
          className="ml-2.5 flex shrink-0 items-center gap-2 whitespace-nowrap"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-umber" aria-hidden="true" />
          <span className="label text-obsidian/60 transition-colors hover:text-obsidian">Availability</span>
        </button>

        <div
          className={cn(
            "hidden items-center gap-4 overflow-hidden transition-all duration-500 ease-out md:flex",
            expanded
              ? "max-w-[26rem] opacity-100"
              : "max-w-0 opacity-0 group-hover:max-w-[26rem] group-hover:opacity-100 group-focus-within:max-w-[26rem] group-focus-within:opacity-100",
          )}
        >
          <label className="flex flex-col gap-0.5">
            <span className="label text-[0.5625rem] text-obsidian/45">In</span>
            <input
              type="date"
              min={today}
              value={stay.checkIn}
              onChange={(event) => onChange({ ...stay, checkIn: event.target.value })}
              aria-label="Check-in date"
              className="w-[7.5rem] border-0 bg-transparent p-0 text-sm text-obsidian focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="label text-[0.5625rem] text-obsidian/45">Out</span>
            <input
              type="date"
              min={stay.checkIn || today}
              value={stay.checkOut}
              onChange={(event) => onChange({ ...stay, checkOut: event.target.value })}
              aria-label="Check-out date"
              className="w-[7.5rem] border-0 bg-transparent p-0 text-sm text-obsidian focus:outline-none"
            />
          </label>
          <label className="flex flex-col gap-0.5">
            <span className="label text-[0.5625rem] text-obsidian/45">Guests</span>
            <select
              value={stay.guests}
              onChange={(event) => onChange({ ...stay, guests: Number(event.target.value) })}
              aria-label="Guests"
              className="w-[3.5rem] border-0 bg-transparent p-0 text-sm text-obsidian focus:outline-none"
            >
              <option value={1}>1</option>
              <option value={2}>2</option>
              <option value={3}>3</option>
              <option value={4}>4</option>
            </select>
          </label>
        </div>

        <button
          type="button"
          onClick={onReserve}
          className="label ml-auto shrink-0 rounded-full bg-obsidian px-5 py-2.5 text-parchment transition-colors hover:bg-umber"
        >
          Reserve
        </button>
      </div>
    </div>
  )
}
