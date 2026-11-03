/** The Thalace mark, as in the app: an orange square as tall as the
 * wordmark's capitals, standing on its baseline, then "Thalace".
 *
 * Sized so the two match to the pixel. Funnel Sans capitals are 0.680em tall,
 * so at 22px they are 15px; browsers draw the square and the letters'
 * baseline at whole pixels, so a size whose capitals fall between pixels
 * makes the square miss the T by one. Change both sizes together. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-baseline gap-1.5 text-[22px] leading-none tracking-tight ${className}`}>
      <span aria-hidden className="inline-block size-[15px] rounded-[2px] bg-brand" />
      Thalace
    </span>
  )
}
