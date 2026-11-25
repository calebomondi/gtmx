import { houseNotes } from "@/lib/content"
import { Reveal } from "@/components/Reveal"

/** Practical notes, kept in the same voice as everything else. */
export function HouseNotes() {
  return (
    <section className="px-[7vw] pb-[14vh] pt-[6vh] md:pb-[18vh]">
      <div className="horizon" />
      <div className="mt-10 grid gap-10 md:grid-cols-3 md:gap-[4vw]">
        {houseNotes.map((note, index) => (
          <Reveal key={note.label} delay={index * 90}>
            <p className="label text-umber">{note.label}</p>
            <p className="mt-4 max-w-sm text-obsidian/70">{note.body}</p>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
