import { Skeleton } from "@/components/ui/skeleton"

export function CompetitionSkeleton() {
  return (
    <div className="w-full flex  flex-col gap-2 items-center justify-center">
        <div className="w-full flex flex-col gap-2 items-center justify-center">
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full" />
                <Skeleton className="h-4.5 w-1/5" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full invisible" />
                <Skeleton className="h-4.5 w-1/5 invisible" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full invisible" />
                <Skeleton className="h-4.5 w-1/5 invisible" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
        </div>
        <div className="w-full flex flex-col gap-2 items-center justify-center">
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full" />
                <Skeleton className="h-4.5 w-1/5" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full invisible" />
                <Skeleton className="h-4.5 w-1/5 invisible" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
            <div className="flex w-full justify-center max-w-xs flex gap-2">
                <Skeleton className="h-4.5 w-4.5 rounded-full invisible" />
                <Skeleton className="h-4.5 w-1/5 invisible" />
                <Skeleton className="h-4.5 w-3/4" />
            </div>
        </div>
    </div>
  )
}
