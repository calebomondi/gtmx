/** The Thalace mark, as in the app: an orange square as tall as the
 * wordmark's capitals, sitting on its baseline, then "Thalace". Sized in em,
 * so the square and the T match at any size. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-baseline gap-[0.28em] text-[1.35rem] leading-none tracking-tight ${className}`}>
      {/* An empty inline-block sits on the baseline; 0.71em is Geist’s cap height. */}
      <span aria-hidden className="inline-block size-[0.71em] rounded-[0.09em] bg-brand" />
      Thalace
    </span>
  )
}
