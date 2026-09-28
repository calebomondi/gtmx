import { Skeleton } from "@/components/ui/skeleton"

export function MarketSkeleton() {
  return (
    <div className="w-full flex flex-col gap-2 items-center justify-center">
        <div className="flex w-full justify-center max-w-xs flex gap-2">
            <Skeleton className="h-4.5 w-1/4" />
            <Skeleton className="h-4.5 w-1/2" />
        </div>
        <div className="flex w-full justify-center max-w-xs flex gap-2">
            <Skeleton className="h-4.5 w-1/4" />
            <Skeleton className="h-4.5 w-1/2" />
        </div>
        <div className="flex w-full justify-center max-w-xs flex gap-2">
            <Skeleton className="h-4.5 w-1/4" />
            <Skeleton className="h-4.5 w-1/2" />
        </div>
        <div className="flex w-full justify-center max-w-xs flex gap-2">
            <Skeleton className="h-4.5 w-1/4" />
            <Skeleton className="h-4.5 w-1/2" />
        </div>
        <div className="flex w-full justify-center max-w-xs flex gap-2">
            <Skeleton className="h-4.5 w-1/4" />
            <Skeleton className="h-4.5 w-1/2" />
        </div>
    </div>
  )
}
