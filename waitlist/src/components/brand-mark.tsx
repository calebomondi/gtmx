/** The GTMX mark, as in the app: an orange square, then "gtmx" in lowercase. */
export function BrandMark({ className = '' }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 ${className}`}>
      <span aria-hidden className="size-4 rounded-[2px] bg-brand" />
      <span className="text-[1.35rem] leading-none tracking-tight">gtmx</span>
    </span>
  )
}
