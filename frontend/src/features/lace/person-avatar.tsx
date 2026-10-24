import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"

/** Up to two initials from a name, else the email's first letter. */
function initials(name: string | null, email: string | null): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean)
  if (words.length > 0) return words.slice(0, 2).map((w) => w[0]).join("").toUpperCase()
  return (email ?? "?")[0].toUpperCase()
}

/** Someone on a Lace: their picture, else their initials. */
export function PersonAvatar({ name, email, avatarUrl, size = "default", className }: {
  name: string | null
  email: string | null
  avatarUrl: string | null
  size?: "default" | "sm" | "lg"
  className?: string
}) {
  return (
    <Avatar size={size} className={className} title={name ?? email ?? undefined}>
      {avatarUrl && <AvatarImage src={avatarUrl} alt="" />}
      <AvatarFallback className="text-xs">{initials(name, email)}</AvatarFallback>
    </Avatar>
  )
}
