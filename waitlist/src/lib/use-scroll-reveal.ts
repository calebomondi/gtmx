import { useEffect } from 'react'

const SELECTOR = '[data-reveal], [data-draw], [data-dots]'

/** Reveal marked elements as they scroll into view, once each. Marks:
 * `data-reveal` (fade and rise; `--i` staggers siblings), `data-draw` (a line
 * draws itself), `data-dots` (pilot dots fill in). Elements rendered later
 * (e.g. once the pilot count loads) are picked up too. The page marks <html>
 * with `.js` first, so without this script nothing is ever hidden. */
export function useScrollReveal() {
  useEffect(() => {
    const show = (el: Element) => el.classList.add('is-visible')
    if (!('IntersectionObserver' in window)) {
      document.querySelectorAll(SELECTOR).forEach(show)
      return
    }
    const seen = new WeakSet<Element>()
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            show(entry.target)
            observer.unobserve(entry.target)
          }
        }
      },
      { rootMargin: '0px 0px -10% 0px', threshold: 0.12 },
    )
    const watch = (root: ParentNode) => {
      root.querySelectorAll(SELECTOR).forEach((el) => {
        if (!seen.has(el)) {
          seen.add(el)
          observer.observe(el)
        }
      })
    }
    watch(document)
    const added = new MutationObserver(() => watch(document))
    added.observe(document.body, { childList: true, subtree: true })
    return () => {
      added.disconnect()
      observer.disconnect()
    }
  }, [])
}
