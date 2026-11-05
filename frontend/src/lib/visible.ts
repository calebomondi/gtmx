/** `fn`, run only while the page is visible: a poll in a hidden tab (another
 * tab in front, the laptop asleep) asks the API nothing, and its next tick
 * after the founder comes back catches up. */
export function whileVisible(fn: () => void): () => void {
  return () => {
    if (!document.hidden) fn()
  }
}
