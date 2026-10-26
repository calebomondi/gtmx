import { useEffect, useState } from 'react'

const EVERY_MS = 2400

function prefersStill(): boolean {
  return typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
}

/** The end of a sentence that changes, one word after another, under a marker
 * highlight. Screen readers, and anyone who prefers less motion, get `whole`
 * instead: the sentence with every word in it. */
export function RotatingWord({ words, whole }: { words: string[]; whole: string }) {
  const [still] = useState(prefersStill)
  const [index, setIndex] = useState(0)

  useEffect(() => {
    if (still) return
    const timer = window.setInterval(() => setIndex((i) => (i + 1) % words.length), EVERY_MS)
    return () => window.clearInterval(timer)
  }, [still, words.length])

  if (still) return <span className="marker">{whole}</span>
  return (
    <>
      <span className="sr-only">{whole}</span>
      <span aria-hidden className="relative inline-block whitespace-nowrap">
        {/* Remounts per word, so each one rises in. */}
        <span key={index} className="marker word-in inline-block">{words[index]}</span>
      </span>
    </>
  )
}
