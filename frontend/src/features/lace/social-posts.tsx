import { ExternalLink, Eye, Heart, MessageCircle, Repeat2 } from "lucide-react"

import { buttonVariants } from "@/components/ui/button"
import type { SocialPostDto } from "@/lib/api"
import { formatRelativeTime } from "@/lib/format"

function Metric({ icon: Icon, value, label }: { icon: typeof Eye; value: number | null; label: string }) {
  if (value === null) return null
  return (
    <span className="inline-flex items-center gap-1 tabular-nums" title={label}>
      <Icon className="size-3.5" aria-hidden /> {value.toLocaleString()}
      <span className="sr-only">{label}</span>
    </span>
  )
}

/** The founder's recent posts on one platform and how each did, newest first. */
export function SocialPosts({ posts, name }: { posts: SocialPostDto[]; name: string }) {
  if (posts.length === 0) {
    return (
      <p className="rounded-xl border border-dashed p-6 text-center text-sm text-muted-foreground">
        No posts read yet. {name} reads your recent posts and how they did in its daily listen.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-2">
      {posts.map((post) => (
        <li key={post.id} className="flex flex-col gap-2 rounded-xl border bg-card p-3">
          <p className="line-clamp-3 text-sm whitespace-pre-line">{post.text || "(no caption)"}</p>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {post.posted_at && <span>{formatRelativeTime(Date.parse(post.posted_at))}</span>}
            <Metric icon={Eye} value={post.views} label="views" />
            <Metric icon={Heart} value={post.likes} label="likes" />
            <Metric icon={MessageCircle} value={post.comments} label="comments" />
            <Metric icon={Repeat2} value={post.shares} label="shares" />
            <a href={post.url} target="_blank" rel="noreferrer"
               className={buttonVariants({ size: "sm", variant: "ghost", className: "ml-auto h-7" })}>
              <ExternalLink /> Open
            </a>
          </div>
        </li>
      ))}
    </ul>
  )
}
