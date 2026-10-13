import { BrandMark } from './brand-mark'

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-ink/10 bg-paper/90 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-5 sm:px-8">
        <a href="#top" aria-label="GTMX home">
          <BrandMark />
        </a>
        <nav className="flex items-center gap-5 text-sm">
          <a href="#what-you-get" className="hidden text-muted hover:text-ink sm:inline">What you get</a>
          <a href="#pilot" className="hidden text-muted hover:text-ink sm:inline">Pilot</a>
          <a href="#join" className="btn-primary px-3.5 py-1.5 text-sm">
            Join the waitlist
          </a>
        </nav>
      </div>
    </header>
  )
}
