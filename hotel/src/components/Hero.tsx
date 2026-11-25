import { images } from "@/lib/content"

/** View A — the atmospheric entrance. The wordmark frames the image. */
export function Hero() {
  return (
    <section id="top" className="relative h-[100svh] min-h-[34rem] w-full overflow-hidden bg-obsidian">
      <img
        src={images.hero}
        alt="Morning light falling across a stone interior"
        className="absolute inset-0 h-full w-full object-cover"
        fetchPriority="high"
      />
      <div className="absolute inset-0 bg-gradient-to-b from-obsidian/60 via-obsidian/10 to-obsidian/65" />

      <div className="relative flex h-full flex-col justify-between px-[6vw] pb-[18vh] pt-[11vh]">
        <div className="flex items-start justify-between gap-6">
          <p aria-hidden="true" className="display text-[clamp(2.6rem,9vw,9rem)] text-parchment">
            DERFED
          </p>
          <p className="label mt-2 hidden max-w-[9rem] text-right text-parchment/70 sm:block">
            Lamu Island
            <br />
            Est. 1911
          </p>
        </div>

        <div className="flex items-end justify-between gap-6">
          <p className="label hidden max-w-[10rem] text-parchment/70 sm:block">
            A sensory
            <br />
            sanctuary
          </p>
          <p aria-hidden="true" className="display ml-auto text-right text-[clamp(2.2rem,8vw,8rem)] text-parchment">
            DELICASIES
          </p>
        </div>
      </div>

      <h1 className="sr-only">Derfed Delicasies — a sensory sanctuary in Lamu, Kenya</h1>
    </section>
  )
}
