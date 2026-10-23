import { Lace } from './lace-mascot'

/** The Thalace mark, as in the app: Lace, then the "Thalace" wordmark. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <Lace state="idle" size={22} decorative />
      <span className="text-[1.35rem] leading-none tracking-tight">Thalace</span>
    </span>
  )
}
