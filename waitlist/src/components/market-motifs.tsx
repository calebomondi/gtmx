/** One line-art motif per market, drawn in the signature orange. Decorative:
 * hidden from screen readers. */

const common = {
  viewBox: '0 0 240 96',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 2,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
  'aria-hidden': true,
  className: 'h-full w-full',
}

/** Kenya: an acacia on the savannah under a low sun. */
export function KenyaMotif() {
  return (
    <svg {...common}>
      <circle cx="182" cy="40" r="16" fill="currentColor" fillOpacity="0.25" />
      <path d="M8 78 C 60 70, 120 74, 232 70" />
      <path d="M78 77 L 82 50 M 82 50 L 70 40 M 82 50 L 96 38" />
      <path d="M44 38 C 60 26, 116 24, 130 36 C 112 42, 64 44, 44 38 Z" fill="currentColor" fillOpacity="0.18" />
      <path d="M150 74 l 3 -8 M 160 73 l 2 -6 M 206 71 l 3 -9" />
    </svg>
  )
}

/** Nigeria: a long bridge striding over the Lagos lagoon. */
export function NigeriaMotif() {
  return (
    <svg {...common}>
      <path d="M8 46 H 232" />
      <path d="M20 46 Q 40 66 60 46 Q 80 66 100 46 Q 120 66 140 46 Q 160 66 180 46 Q 200 66 220 46" />
      <path d="M40 46 V 60 M 80 46 V 60 M 120 46 V 60 M 160 46 V 60 M 200 46 V 60" />
      <path d="M8 72 c 12 -5 24 5 36 0 s 24 -5 36 0 s 24 5 36 0 s 24 -5 36 0 s 24 5 36 0 s 24 -5 36 0" strokeOpacity="0.6" />
      <path d="M26 84 c 12 -5 24 5 36 0 s 24 -5 36 0 s 24 5 36 0 s 24 -5 36 0 s 24 5 36 0" strokeOpacity="0.35" />
    </svg>
  )
}

/** South Africa: Table Mountain's flat top, with its tablecloth of cloud. */
export function SouthAfricaMotif() {
  return (
    <svg {...common}>
      <path d="M8 80 L 46 52 L 70 30 H 168 L 188 50 L 232 80" fill="currentColor" fillOpacity="0.18" />
      <path d="M8 80 H 232" />
      <path d="M78 30 c 6 -8 18 -8 22 -2 c 6 -6 18 -4 20 4 c 8 -6 22 -2 22 6" strokeOpacity="0.7" />
      <path d="M196 56 L 212 44 L 226 58" />
    </svg>
  )
}
