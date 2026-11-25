import { useCallback, useState } from "react"
import { AvailabilityBar } from "@/components/AvailabilityBar"
import { BookingPanel } from "@/components/BookingPanel"
import { ExploreCurtain } from "@/components/ExploreCurtain"
import { FinalImpression } from "@/components/FinalImpression"
import { Frame } from "@/components/Frame"
import { GastronomyGallery } from "@/components/GastronomyGallery"
import { Hero } from "@/components/Hero"
import { HouseNotes } from "@/components/HouseNotes"
import { Manifesto } from "@/components/Manifesto"
import { Rooms } from "@/components/Rooms"
import { SiteHeader } from "@/components/SiteHeader"
import type { RoomId, Stay } from "@/lib/content"

export default function App() {
  const [stay, setStay] = useState<Stay>({ checkIn: "", checkOut: "", guests: 2, roomId: null })
  const [bookingOpen, setBookingOpen] = useState(false)
  const [exploreOpen, setExploreOpen] = useState(false)

  const openBooking = useCallback((roomId?: RoomId) => {
    if (roomId) setStay((current) => ({ ...current, roomId }))
    setBookingOpen(true)
  }, [])

  return (
    <div className="grain min-h-screen bg-parchment text-obsidian">
      <SiteHeader onReserve={() => openBooking()} />
      <Frame />

      <main>
        <Hero />
        <Manifesto />
        <GastronomyGallery />
        <Rooms onReserve={openBooking} />
        <HouseNotes />
      </main>

      <FinalImpression onReserve={() => openBooking()} />

      <AvailabilityBar stay={stay} onChange={setStay} onReserve={() => openBooking()} />
      <ExploreCurtain open={exploreOpen} onChange={setExploreOpen} onReserve={() => openBooking()} />
      <BookingPanel
        open={bookingOpen}
        stay={stay}
        onChange={setStay}
        onClose={() => setBookingOpen(false)}
      />
    </div>
  )
}
