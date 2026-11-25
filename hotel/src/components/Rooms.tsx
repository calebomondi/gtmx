import { cn } from "@/lib/cn"
import { currency, rooms, type Room, type RoomId } from "@/lib/content"
import { Reveal } from "@/components/Reveal"
import { SectionMark } from "@/components/SectionMark"

type Props = {
  onReserve: (roomId: RoomId) => void
}

/** View C — rooms presented as case studies with a technical specification list. */
export function Rooms({ onReserve }: Props) {
  return (
    <section id="rooms" className="px-[7vw] py-[14vh] md:py-[18vh]">
      <SectionMark index="03" title="The Rooms" />

      <div className="mt-12 grid gap-6 md:mt-20 md:grid-cols-12">
        <h2 className="display text-[clamp(2rem,4.6vw,4.4rem)] md:col-span-8">
          Three ways to sleep, and none of them hurried.
        </h2>
        <p className="max-w-sm self-end text-obsidian/65 md:col-span-4">
          Each room is described the way we would describe it to a friend: by surface, scent, sound,
          and the hour the light is best.
        </p>
      </div>

      <div className="mt-16 space-y-[12vh] md:mt-24 md:space-y-[16vh]">
        {rooms.map((room, index) => (
          <RoomCaseStudy key={room.id} room={room} flip={index % 2 === 1} onReserve={onReserve} />
        ))}
      </div>
    </section>
  )
}

type CaseProps = {
  room: Room
  flip: boolean
  onReserve: (roomId: RoomId) => void
}

function RoomCaseStudy({ room, flip, onReserve }: CaseProps) {
  return (
    <Reveal>
      <article className="group grid gap-8 md:grid-cols-12 md:items-end md:gap-[4vw]">
        <div
          className={cn(
            "relative overflow-hidden bg-mist md:col-span-7",
            flip ? "md:order-2 md:col-start-6" : "md:col-start-1",
          )}
        >
          <img
            src={room.image}
            alt={`${room.name}, in daylight`}
            loading="lazy"
            className="aspect-[4/5] w-full object-cover transition-transform duration-[1400ms] ease-out group-hover:scale-[1.02]"
          />
          {/* The Light Shift: the same room, graded for the hour after dinner. */}
          <img
            src={room.image}
            alt=""
            aria-hidden="true"
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover opacity-0 brightness-[0.42] contrast-[1.08] saturate-[0.72] transition-opacity duration-700 ease-out group-hover:opacity-100 group-focus-within:opacity-100"
          />
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_72%_28%,rgba(140,94,60,0.5),transparent_58%)] opacity-0 transition-opacity duration-700 group-hover:opacity-100 group-focus-within:opacity-100"
          />
          <span className="label absolute left-4 top-4 text-parchment/80 mix-blend-difference">
            {room.numeral}
          </span>
        </div>

        <div className={cn("md:col-span-4", flip ? "md:order-1 md:col-start-1" : "md:col-start-9")}>
          <div className="flex items-baseline justify-between gap-4">
            <h3 className="display text-[clamp(1.7rem,3vw,2.6rem)]">{room.name}</h3>
            <span className="label text-obsidian/40">{room.numeral}</span>
          </div>
          <p className="mt-3 text-obsidian/65">{room.tagline}</p>

          <dl className="mt-6 border-y border-obsidian/15 text-sm">
            {room.specs.map((spec) => (
              <div key={spec.label} className="flex justify-between gap-6 border-b border-obsidian/10 py-2.5 last:border-b-0">
                <dt className="label text-obsidian/40">{spec.label}</dt>
                <dd className="text-right text-obsidian/80">{spec.value}</dd>
              </div>
            ))}
          </dl>

          <div className="mt-6 flex items-center justify-between gap-4">
            <p className="label text-obsidian/50">
              From {currency.format(room.price)} / night
            </p>
            <button
              type="button"
              onClick={() => onReserve(room.id)}
              className="label rounded-full border border-obsidian/25 px-5 py-2.5 transition-colors hover:border-umber hover:bg-umber hover:text-parchment"
            >
              Reserve
            </button>
          </div>
        </div>
      </article>
    </Reveal>
  )
}
