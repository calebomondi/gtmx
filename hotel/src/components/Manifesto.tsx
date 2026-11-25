import { images } from "@/lib/content"
import { Parallax } from "@/components/Parallax"
import { Reveal } from "@/components/Reveal"
import { SectionMark } from "@/components/SectionMark"

export function Manifesto() {
  return (
    <section className="px-[7vw] py-[14vh] md:py-[20vh]">
      <SectionMark index="01" title="The House" />

      <div className="mt-12 grid gap-12 md:mt-20 md:grid-cols-12 md:gap-[4vw]">
        <div className="md:col-span-7">
          <Parallax speed={0.04}>
            <p className="display text-[clamp(1.9rem,4.1vw,4rem)]">
              A house built from what the island had: coral, lime, and time.
            </p>
          </Parallax>

          <Reveal className="mt-8 md:mt-14">
            <p className="max-w-xl text-obsidian/70">
              DERFED DELICASIES is nine rooms on the edge of Lamu's old stone town, arranged around a
              courtyard that stays cool until dusk. The kitchen keeps its own hours, the linen is
              changed daily, and nothing is served that did not arrive that morning.
            </p>
            <p className="mt-5 max-w-xl text-obsidian/70">
              We do not have a lobby, a television, or a schedule. We have a table, a roof terrace, and
              the slow art of being looked after.
            </p>
          </Reveal>

          <dl className="mt-10 grid grid-cols-2 gap-y-5 border-t border-obsidian/15 pt-6 sm:grid-cols-4">
            {[
              { term: "Rooms", value: "Nine" },
              { term: "The Table", value: "20 seats" },
              { term: "Built", value: "1911" },
              { term: "Open", value: "All year" },
            ].map((item) => (
              <div key={item.term}>
                <dt className="label text-obsidian/45">{item.term}</dt>
                <dd className="display mt-1 text-2xl">{item.value}</dd>
              </div>
            ))}
          </dl>
        </div>

        <Reveal className="md:col-span-5 md:pt-[8vh]" delay={120}>
          <figure>
            <img
              src={images.house}
              alt="The east wall of the house, cut from coral and lime"
              className="aspect-[4/5] w-full object-cover"
              loading="lazy"
            />
            <figcaption className="label mt-3 text-obsidian/45">
              The east wall, at eleven in the morning
            </figcaption>
          </figure>
        </Reveal>
      </div>
    </section>
  )
}
