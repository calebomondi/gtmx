import { Closing } from './components/closing'
import { Faq } from './components/faq'
import { FoundingTeams } from './components/founding-teams'
import { Hero } from './components/hero'
import { HowItWorks } from './components/how-it-works'
import { Pilot } from './components/pilot'
import { SiteHeader } from './components/site-header'
import { WhatLaceDoes } from './components/what-lace-does'
import { YourTools } from './components/your-tools'
import { Worldwide } from './components/worldwide'
import { usePilotSpots } from './lib/use-pilot-spots'
import { useScrollReveal } from './lib/use-scroll-reveal'

export default function App() {
  const [pilot, setPilotSpotsLeft] = usePilotSpots()
  useScrollReveal()
  return (
    <>
      <SiteHeader />
      <main>
        <Hero pilot={pilot} onPilotSpotsLeft={setPilotSpotsLeft} />
        <WhatLaceDoes />
        <FoundingTeams />
        <HowItWorks />
        <YourTools />
        <Worldwide />
        <Pilot pilot={pilot} />
        <Faq />
      </main>
      <Closing pilot={pilot} onPilotSpotsLeft={setPilotSpotsLeft} />
    </>
  )
}
