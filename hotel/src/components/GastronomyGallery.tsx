import { useEffect, useRef, useState } from "react"
import { gallery } from "@/lib/content"
import { useMediaQuery } from "@/lib/hooks"
import { SectionMark } from "@/components/SectionMark"

/**
 * View B — the chef's table scroll. Vertical page scroll is translated into a
 * horizontal drift across macro ingredients and the suites they end up in.
 * Below md the section falls back to a native horizontal snap row.
 */
export function GastronomyGallery() {
  const sectionRef = useRef<HTMLElement>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const isDesktop = useMediaQuery("(min-width: 768px)")
  const [progress, setProgress] = useState(0)
  const [maxShift, setMaxShift] = useState(0)

  useEffect(() => {
    if (!isDesktop) {
      setProgress(0)
      setMaxShift(0)
      return
    }

    let frame = 0
    const update = () => {
      frame = 0
      const section = sectionRef.current
      if (!section) return
      const distance = section.offsetHeight - window.innerHeight
      if (distance <= 0) return
      const rect = section.getBoundingClientRect()
      setProgress(Math.min(1, Math.max(0, -rect.top / distance)))
    }
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update)
    }

    update()
    window.addEventListener("scroll", onScroll, { passive: true })
    window.addEventListener("resize", onScroll)
    return () => {
      window.removeEventListener("scroll", onScroll)
      window.removeEventListener("resize", onScroll)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [isDesktop])

  useEffect(() => {
    const measure = () => {
      const track = trackRef.current
      if (!track || !isDesktop) {
        setMaxShift(0)
        return
      }
      setMaxShift(Math.max(0, track.scrollWidth - window.innerWidth))
    }
    measure()
    window.addEventListener("resize", measure)
    return () => window.removeEventListener("resize", measure)
  }, [isDesktop])

  return (
    <section id="table" ref={sectionRef} className="relative bg-obsidian text-parchment md:h-[340vh]">
      <div className="md:sticky md:top-0 md:flex md:h-screen md:flex-col md:justify-center md:overflow-hidden">
        <div className="px-[7vw] pt-[14vh] md:pt-0">
          <SectionMark index="02" title="The Table" inverse />
          <div className="mt-8 flex flex-wrap items-end justify-between gap-6">
            <h2 className="display max-w-[18ch] text-[clamp(2rem,5vw,4.6rem)]">
              Everything is served the week it arrives.
            </h2>
            <p className="label max-w-[13rem] text-parchment/50">
              One seating, at eight
              <br />
              Drag or scroll to move through
            </p>
          </div>
        </div>

        <div className="no-scrollbar mt-10 snap-x snap-mandatory overflow-x-auto pb-10 md:mt-[6vh] md:overflow-visible md:pb-0">
          <div
            ref={trackRef}
            className="flex w-max items-end gap-[5vw] px-[7vw] md:gap-[4vw]"
            style={isDesktop ? { transform: `translate3d(${-progress * maxShift}px, 0, 0)` } : undefined}
          >
            {gallery.map((item, index) => (
              <figure
                key={item.caption}
                className={
                  index % 2 === 0
                    ? "w-[min(72vw,24rem)] shrink-0 snap-center md:mb-[9vh]"
                    : "w-[min(72vw,19rem)] shrink-0 snap-center"
                }
              >
                <div className="overflow-hidden bg-obsidian/60">
                  <img
                    src={item.image}
                    alt={item.caption}
                    loading="lazy"
                    className="h-[min(52vh,30rem)] w-full object-cover transition-transform duration-[1200ms] ease-out hover:scale-[1.03]"
                  />
                </div>
                <figcaption className="mt-4 flex items-baseline justify-between gap-4 border-t border-parchment/20 pt-3">
                  <span className="display text-xl">{item.caption}</span>
                  <span className="label text-right text-parchment/45">{item.note}</span>
                </figcaption>
              </figure>
            ))}
          </div>
        </div>

        <div className="hidden px-[7vw] md:block">
          <div className="h-px w-full bg-parchment/15">
            <div
              className="h-px bg-umber transition-[width] duration-150 ease-out"
              style={{ width: `${Math.max(4, progress * 100)}%` }}
            />
          </div>
        </div>
      </div>
    </section>
  )
}
