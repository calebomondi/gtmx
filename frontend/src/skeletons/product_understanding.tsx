import { Skeleton } from "@/components/ui/skeleton"

export function ProductUnderstandSkeleton() {
  return (
    <div className="flex w-full max-w-xs flex-col gap-2">
      <Skeleton className="h-3 w-1/2" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-full" />
      <Skeleton className="h-3 w-3/4" />
    </div>
  )
}
