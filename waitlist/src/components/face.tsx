/** The people in the page's examples, as their avatars in public/people/
 * (Notionists by Zoish via DiceBear, CC0). Kalev is the founder; the other
 * is his cofounder. */
export type Person = 'kalev' | 'cofounder'

/** A person's round avatar. Decorative: the name is always written beside it. */
export function Face({ person, size }: { person: Person; size: number }) {
  return <img src={`/people/${person}.svg`} alt="" width={size} height={size} className="shrink-0 rounded-full" />
}
