/** How much of the backdrop a page gets: chat keeps it quiet so the
 * conversation stays the focus. */
export type BackdropTone = "full" | "calm"

const CHAT_PATH = /^\/lace\/[^/]+\/chat\/?$/

export function backdropTone(pathname: string): BackdropTone {
  return CHAT_PATH.test(pathname) ? "calm" : "full"
}
