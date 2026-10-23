/** The Thalace mark, as in the app: an orange square as tall as the
 * wordmark's capitals, standing on its baseline, then "Thalace".
 *
 * Sized so the two match to the pixel. Geist's capitals are 0.708em tall, so
 * at 21.2px they are 15px; browsers draw the square and the letters' baseline
 * at whole pixels, so at a size like 21.6px (capitals 15.3px) the square comes
 * out 15 or 16px and misses the T by a pixel. Change both sizes together. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-baseline gap-1.5 text-[21.2px] leading-none tracking-tight ${className}`}>
      <span aria-hidden className="inline-block size-[15px] rounded-[2px] bg-brand" />
      Thalace
    </span>
  )
}
