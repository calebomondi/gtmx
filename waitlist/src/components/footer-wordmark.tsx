/** The footer's signature: the mark at poster size, cropped at the bottom and
 * faded so it reads as texture rather than a second headline. Decorative.
 * Sized in em from one clamp(), so the square, letters and crop scale as one
 * and never exceed the container (no sideways scroll on phones). */
export function FooterWordmark() {
  return (
    <div
      aria-hidden="true"
      className="group mx-auto max-w-7xl overflow-hidden px-5 select-none sm:px-8"
      style={{ fontSize: 'clamp(6rem, 25vw, 21rem)' }}
    >
      {/* 0.8 line-height, cropped to ~85% of it: the bottom bleeds off. */}
      <div
        className="flex h-[0.68em] items-start justify-center gap-[0.09em] leading-[0.8] font-semibold tracking-[-0.06em]"
        style={{ maskImage: 'linear-gradient(to bottom, #000 45%, transparent)' }}
      >
        <span className="mt-[0.25em] size-[0.52em] shrink-0 rounded-[0.05em] bg-brand/25 transition-colors duration-700 group-hover:bg-brand/70" />
        <span className="text-paper/[0.07] transition-colors duration-700 group-hover:text-paper/[0.12]">gtmx</span>
      </div>
    </div>
  )
}
