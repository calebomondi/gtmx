/** One of the page's background shapes: Lace's own rounded square, in
 * translucent orange, so where two overlap the colour deepens. Placed and
 * sized by the section that draws it (`className`), inside its `decor`. */
export function LaceSquare({ className = '' }: { className?: string }) {
  return <span className={`lace-square ${className}`} />
}
