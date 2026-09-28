import { Skeleton } from "@/components/ui/skeleton"

const ACCOUNTS = 3

export function SpecialistsSkeleton() {
  return (
    <div className="flex flex-col gap-2">
      {Array.from({ length: ACCOUNTS }, (_, index) => (
        <div key={index} className="my-1.5 flex items-center gap-3">
          <Skeleton className="h-10 w-10 rounded-full" />
          <div className="space-y-1.5">
            <Skeleton className="h-3 w-[160px]" />
            <Skeleton className="h-3 w-[160px]" />
            <Skeleton className="h-3 w-[200px]" />
          </div>
        </div>
      ))}
    </div>
  )
}
