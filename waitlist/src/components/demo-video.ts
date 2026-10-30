/** The product recording shown in the hero. While `DEMO_VIDEO` is null the
 * hero shows a screenshot of the app instead (`AppShot`).
 *
 * To publish a recording: run scripts/encode-demo.sh on the raw capture
 * (it writes public/media/demo.{mp4,webm} and demo-poster.webp), then fill
 * this in, with captions timed to the clip. */

export interface DemoCaption {
  /** Seconds into the clip when this caption appears. */
  at: number
  text: string
}

export interface DemoVideo {
  /** What the recording shows, e.g. "Shanga Labs". */
  subject: string
  mp4: string
  webm: string
  poster: string
  captions: DemoCaption[]
}

export const DEMO_VIDEO: DemoVideo | null = null
