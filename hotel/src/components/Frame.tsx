/**
 * The gallery wall: a structural hairline frame inset 2vw from the viewport,
 * drawn above the page so imagery bleeds underneath it.
 */
export function Frame() {
  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 z-[55]">
      <div className="absolute inset-[2vw] border border-obsidian/20" />
      <span className="absolute left-[2vw] top-[2vw] h-2 w-2 -translate-x-1/2 -translate-y-1/2 bg-obsidian/70" />
      <span className="absolute right-[2vw] top-[2vw] h-2 w-2 -translate-y-1/2 translate-x-1/2 bg-obsidian/70" />
      <span className="absolute bottom-[2vw] left-[2vw] h-2 w-2 -translate-x-1/2 translate-y-1/2 bg-obsidian/70" />
      <span className="absolute bottom-[2vw] right-[2vw] h-2 w-2 translate-x-1/2 translate-y-1/2 bg-obsidian/70" />
    </div>
  )
}
