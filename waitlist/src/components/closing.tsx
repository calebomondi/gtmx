import { BrandMark } from './brand-mark'

export function Closing() {
  return (
    <footer className="border-t border-line">
      <div className="mx-auto flex max-w-6xl flex-col gap-10 px-5 py-16 sm:px-8 sm:py-20">
        <div className="flex flex-col items-start gap-5">
          <h2 className="max-w-2xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
            Stop guessing who to sell to.
          </h2>
          <a href="#join" className="rounded-md bg-ink px-5 py-3 text-sm font-semibold text-paper hover:bg-ink/85">
            Join the waitlist
          </a>
        </div>
        <div className="flex flex-col gap-3 border-t border-line pt-6 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
          <BrandMark className="text-ink" />
          <p>For founders selling across Africa.</p>
        </div>
      </div>
    </footer>
  )
}
