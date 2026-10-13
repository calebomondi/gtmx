import { BrandMark } from './brand-mark'

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-10 border-b border-line/70 bg-paper/85 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-5 sm:px-8">
        <a href="#top" aria-label="GTMX home">
          <BrandMark />
        </a>
        <nav className="flex items-center gap-5 text-sm">
          <a href="#what-you-get" className="hidden text-muted hover:text-ink sm:inline">What you get</a>
          <a href="#pilot" className="hidden text-muted hover:text-ink sm:inline">Pilot</a>
          <a href="#join" className="rounded-md bg-ink px-3.5 py-1.5 font-medium text-paper hover:bg-ink/85">
            Join the waitlist
          </a>
        </nav>
      </div>
    </header>
  )
}
