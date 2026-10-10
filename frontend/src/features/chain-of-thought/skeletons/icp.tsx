import { Skeleton } from "@/components/ui/skeleton"

export function IcpSkeleton() {
  return (
    <div className="flex w-full flex-col items-center justify-center gap-2">
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
      <div className="flex w-full justify-between gap-2">
        <Skeleton className="h-4.5 w-1/4" />
        <Skeleton className="h-4.5 w-2/3" />
      </div>
    </div>
  )
}