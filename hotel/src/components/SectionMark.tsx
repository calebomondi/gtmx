import { cn } from "@/lib/cn"

type Props = {
  index: string
  title: string
  inverse?: boolean
}

/** A numbered section marker sitting on the Horizon Line. */
export function SectionMark({ index, title, inverse = false }: Props) {
  return (
    <div className="flex items-center gap-5">
      <span className={cn("label", inverse ? "text-parchment/70" : "text-umber")}>{index}</span>
      <span className={cn("flex-1", inverse ? "horizon-inverse" : "horizon")} />
      <span className={cn("label", inverse ? "text-parchment/50" : "text-obsidian/45")}>{title}</span>
    </div>
  )
}
