import { Markdown } from "@/components/ui/markdown"
import { cn } from "@/lib/utils"

// A reply reads as one flow: Markdown's own flex column keeps each block's
// margins apart (flex items' margins never collapse), which doubled every
// gap. As a block, neighbouring margins collapse into one even gap. Lists
// stay tight even when the model leaves blank lines between items (a
// "loose" list wraps each item in a paragraph).
const REPLY_PROSE = cn(
  "prose prose-sm dark:prose-invert block min-w-0 max-w-none leading-relaxed",
  "prose-p:my-2.5 prose-ul:my-2.5 prose-ol:my-2.5 prose-li:my-1 [&_li>p]:my-0 prose-ul:pl-5 prose-ol:pl-5",
  "prose-headings:mt-4 prose-headings:mb-1.5 prose-h1:text-base prose-h2:text-base prose-h3:text-sm",
  "prose-hr:my-4 prose-pre:my-3 prose-blockquote:my-3 prose-table:my-3",
  "[&>:first-child]:mt-0 [&>:last-child]:mb-0",
)

/** More than one blank line says nothing more than one. */
function tidy(text: string): string {
  return text.replace(/\n{3,}/g, "\n\n").trim()
}

/** A Lace's words (a reply, a brief) as markdown, evenly spaced. */
export function ReplyMarkdown({ children, className }: { children: string; className?: string }) {
  return <Markdown className={cn(REPLY_PROSE, className)}>{tidy(children)}</Markdown>
}
