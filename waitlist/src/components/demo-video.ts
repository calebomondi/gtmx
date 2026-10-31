/** The hero's recording: the real app, Thalace's own Lace in its team chat,
 * with example data. scripts/record-demo.mjs records and encodes both cuts
 * into public/media/ and prints when each moment happens; the captions below
 * are timed to those. */

export interface DemoCaption {
  /** Seconds into the clip when this caption appears. */
  at: number
  text: string
}

/** One cut of the recording, with its captions timed to it. */
export interface DemoCut {
  mp4: string
  poster: string
  /** Its shape, width over height. */
  aspect: '4/3' | '3/4'
  captions: DemoCaption[]
}

export interface DemoVideo {
  /** What the recording shows. */
  subject: string
  /** 4:3, from sm up. */
  wide: DemoCut
  /** 3:4, so the chat stays readable on phones. */
  phone: DemoCut
}

const captions = (at: { asks: number; works: number; answers: number; saves: number }): DemoCaption[] => [
  { at: 0, text: 'Kalev asks his Lace' },
  { at: at.works, text: 'It looks, step by step' },
  { at: at.answers, text: 'It answers with why each fits' },
  { at: at.saves, text: 'Saved only on his click' },
]

export const DEMO_VIDEO: DemoVideo = {
  subject: 'Thalace’s own Lace',
  wide: {
    mp4: '/media/demo.mp4',
    poster: '/media/demo-poster.webp',
    aspect: '4/3',
    captions: captions({ asks: 0.9, works: 5.2, answers: 9, saves: 11.4 }),
  },
  phone: {
    mp4: '/media/demo-phone.mp4',
    poster: '/media/demo-phone-poster.webp',
    aspect: '3/4',
    captions: captions({ asks: 0, works: 3.4, answers: 7.2, saves: 10.9 }),
  },
}
