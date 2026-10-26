/** A source the Lace cited in a reply. */
export interface ReplySource {
  /** Its citation number, when the reply numbered it. */
  n: number | null
  label: string
  url: string
  host: string
}

// "Sources", "**Sources**", "## Sources:" alone on a line.
const SOURCES_HEADING = /^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*|__)?Sources(?:\*\*|__)?:?[ \t]*$/im
const LINK = /https?:\/\/[^\s)<>\]"]+/

function host(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, "")
  } catch {
    return url
  }
}

function parseLine(line: string): ReplySource | null {
  const url = line.match(LINK)?.[0]?.replace(/[.,;]+$/, "")
  if (!url) return null
  const n = line.match(/^\s*(?:[-*]\s*)?\[?(\d+)[\].)]/)?.[1]
  const label = line
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")  // markdown links keep their text
    .replace(LINK, "")
    .replace(/^\s*(?:[-*]\s*)?\[?\d+[\].)]\s*/, "")
    .replace(/[\s:–—.,;-]+$/, "")
    .trim()
  return { n: n ? Number(n) : null, label: label || host(url), url, host: host(url) }
}

/** A reply split into what it says and the sources it ends with. The
 * citations in the text ("[1]") become links to their source. A reply with
 * no "Sources" section comes back as it is. */
export function splitSources(markdown: string): { body: string; sources: ReplySource[] } {
  const match = SOURCES_HEADING.exec(markdown)
  if (!match) return { body: markdown, sources: [] }
  const sources = markdown.slice(match.index + match[0].length).split("\n")
    .map(parseLine).filter((s): s is ReplySource => s !== null)
  const byNumber = new Map(sources.filter((s) => s.n !== null).map((s) => [s.n as number, s.url]))
  const body = markdown.slice(0, match.index).trimEnd()
    .replace(/\[(\d+)\](?![(:])/g, (whole, n: string) => {
      const url = byNumber.get(Number(n))
      return url ? `[[${n}]](${url})` : whole
    })
  return { body, sources }
}
