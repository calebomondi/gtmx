import { useState } from "react"
import { images } from "@/lib/content"

type Props = {
  onReserve: () => void
}

function greetingForHour(hour: number) {
  if (hour >= 5 && hour < 12) return { title: "Good morning.", note: "The kitchen is awake. So is the sea." }
  if (hour >= 12 && hour < 17) return { title: "Good afternoon.", note: "Shutters closed, the courtyard at its coolest." }
  if (hour >= 17 && hour < 22) return { title: "Good evening.", note: "One seating at eight. The lamps are lit." }
  return { title: "Goodnight.", note: "The house is quiet. The kitchen is not." }
}

/** The Final Impression: full-bleed night, coordinates, and a greeting by local hour. */
export function FinalImpression({ onReserve }: Props) {
  const [greeting] = useState(() => greetingForHour(new Date().getHours()))

  return (
    <footer id="contact" className="relative overflow-hidden bg-obsidian text-parchment">
      <img
        src={images.night}
        alt="The house at night, lit from within"
        loading="lazy"
        className="absolute inset-0 h-full w-full object-cover opacity-70"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-obsidian/70 via-obsidian/35 to-obsidian/85" />

      <div className="relative flex min-h-[92svh] flex-col justify-between px-[7vw] py-[10vh]">
        <div className="flex items-start justify-between gap-6">
          <p className="label text-parchment/60">
            2°16′S 40°54′E
            <br />
            Lamu Old Town, Kenya
          </p>
          <p className="label text-right text-parchment/60">
            Derfed
            <br />
            Delicasies
          </p>
        </div>

        <div>
          <p className="label text-parchment/60">{greeting.note}</p>
          <h2 className="display mt-4 text-[clamp(2.6rem,9vw,8rem)]">{greeting.title}</h2>
          <button
            type="button"
            onClick={onReserve}
            className="label mt-10 rounded-full bg-parchment px-7 py-3.5 text-obsidian transition-colors hover:bg-umber hover:text-parchment"
          >
            Reserve a room
          </button>
        </div>

        <div className="flex flex-wrap items-end justify-between gap-6 border-t border-parchment/20 pt-6">
          <a
            href="mailto:reservations@derfeddelicasies.com"
            className="label text-parchment/70 transition-colors hover:text-parchment"
          >
            reservations@derfeddelicasies.com
          </a>
          <a href="#top" className="label text-parchment/50 transition-colors hover:text-parchment">
            Back to the top
          </a>
          <p className="label text-parchment/35">© {new Date().getFullYear()} Derfed Delicasies</p>
        </div>
      </div>
    </footer>
  )
}
