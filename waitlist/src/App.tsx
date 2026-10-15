import { Closing } from './components/closing'
import { Faq } from './components/faq'
import { FirstRun } from './components/first-run'
import { Hero } from './components/hero'
import { HowItWorks } from './components/how-it-works'
import { Markets } from './components/markets'
import { Pilot } from './components/pilot'
import { SiteHeader } from './components/site-header'
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
        <FirstRun />
        <HowItWorks />
        <Markets />
        <Pilot pilot={pilot} />
        <Faq />
      </main>
      <Closing pilot={pilot} onPilotSpotsLeft={setPilotSpotsLeft} />
    </>
  )
}
