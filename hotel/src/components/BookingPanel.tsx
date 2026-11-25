import { useEffect, useState } from "react"
import { cn } from "@/lib/cn"
import {
  currency,
  formatStayDate,
  nightsBetween,
  rooms,
  todayISO,
  type Room,
  type Stay,
} from "@/lib/content"

type Props = {
  open: boolean
  stay: Stay
  onChange: (stay: Stay) => void
  onClose: () => void
}

type Guest = { name: string; email: string; notes: string }

const stepTitles = ["Dates", "Room", "Guest", "Review"]
const inputClass =
  "mt-2 w-full border-0 border-b border-obsidian/25 bg-transparent pb-2 font-display text-2xl focus:border-obsidian focus:outline-none"

/**
 * View D — the transactional veil. A glass slide-over over the parchment,
 * with borderless fields separated only by the Horizon Line.
 */
export function BookingPanel({ open, stay, onChange, onClose }: Props) {
  const [step, setStep] = useState(0)
  const [guest, setGuest] = useState<Guest>({ name: "", email: "", notes: "" })
  const [error, setError] = useState<string | null>(null)
  const [reference, setReference] = useState<string | null>(null)

  const room = rooms.find((item) => item.id === stay.roomId) ?? null
  const nights = nightsBetween(stay.checkIn, stay.checkOut)
  const total = room ? room.price * nights : 0

  useEffect(() => {
    if (!open) return
    setStep(0)
    setError(null)
    setReference(null)
  }, [open])

  useEffect(() => {
    if (!open) return
    const previous = document.body.style.overflow
    document.body.style.overflow = "hidden"
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose()
    }
    window.addEventListener("keydown", onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener("keydown", onKey)
    }
  }, [open, onClose])

  const advance = () => {
    if (step === 0) {
      if (!stay.checkIn || !stay.checkOut) {
        setError("Choose an arrival and a departure.")
        return
      }
      if (nights < 1) {
        setError("Departure has to come after arrival.")
        return
      }
    }
    if (step === 1 && !room) {
      setError("Choose a room to continue.")
      return
    }
    if (step === 2) {
      if (!guest.name.trim()) {
        setError("We need a name for the book.")
        return
      }
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(guest.email)) {
        setError("That email address does not look complete.")
        return
      }
    }
    setError(null)
    setStep((current) => Math.min(current + 1, stepTitles.length - 1))
  }

  const submit = () => {
    if (!room) return
    const code = `DD-${Math.random().toString(36).slice(2, 6).toUpperCase()}`
    try {
      const key = "derfed.reservations"
      const existing = JSON.parse(window.localStorage.getItem(key) ?? "[]") as unknown[]
      window.localStorage.setItem(
        key,
        JSON.stringify([
          ...existing,
          { reference: code, room: room.name, nights, total, ...stay, guest, createdAt: new Date().toISOString() },
        ]),
      )
    } catch {
      // Storage can be blocked; the request screen still has to appear.
    }
    setReference(code)
  }

  return (
    <div className={cn("fixed inset-0 z-[80]", !open && "pointer-events-none")} inert={!open}>
      <button
        type="button"
        aria-label="Close reservation panel"
        onClick={onClose}
        className={cn(
          "absolute inset-0 h-full w-full cursor-default bg-obsidian/25 backdrop-blur-[2px] transition-opacity duration-500",
          open ? "opacity-100" : "opacity-0",
        )}
      />

      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Reserve a room"
        className={cn(
          "absolute inset-y-0 right-0 flex w-full max-w-[34rem] flex-col border-l border-obsidian/20 bg-parchment/80 backdrop-blur-[20px] transition-transform duration-500 ease-out",
          open ? "translate-x-0" : "translate-x-full",
        )}
      >
        <header className="flex items-start justify-between gap-6 px-6 pt-6 md:px-9 md:pt-9">
          <div>
            <p className="label text-umber">Reservation</p>
            <p className="display mt-2 text-3xl">{reference ? "Received" : stepTitles[step]}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="label mt-1 text-obsidian/50 transition-colors hover:text-obsidian"
          >
            Close
          </button>
        </header>

        <div className="mt-5 px-6 md:px-9">
          <div className="horizon" />
          <div className="mt-3 flex items-center justify-between gap-4">
            <span className="label text-obsidian/40">{String(step + 1).padStart(2, "0")} / 04</span>
            <span className="label truncate text-obsidian/40">{room ? room.name : "No room chosen"}</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-6 py-8 md:px-9">
          {reference ? (
            <Confirmation
              reference={reference}
              room={room}
              stay={stay}
              nights={nights}
              total={total}
              guest={guest}
            />
          ) : step === 0 ? (
            <DatesStep stay={stay} onChange={onChange} />
          ) : step === 1 ? (
            <RoomStep stay={stay} onChange={onChange} />
          ) : step === 2 ? (
            <GuestStep guest={guest} onChange={setGuest} />
          ) : (
            <ReviewStep room={room} stay={stay} nights={nights} total={total} guest={guest} />
          )}

          {error && (
            <p role="alert" className="mt-6 text-sm text-umber">
              {error}
            </p>
          )}
        </div>

        {!reference && (
          <footer className="border-t border-obsidian/15 px-6 py-5 md:px-9">
            <div className="flex items-center justify-between gap-4">
              <button
                type="button"
                onClick={() => {
                  setError(null)
                  setStep((current) => Math.max(0, current - 1))
                }}
                className={cn("label text-obsidian/50 transition-colors hover:text-obsidian", step === 0 && "invisible")}
              >
                Back
              </button>
              {step < stepTitles.length - 1 ? (
                <button
                  type="button"
                  onClick={advance}
                  className="label rounded-full bg-obsidian px-6 py-3 text-parchment transition-colors hover:bg-umber"
                >
                  Continue
                </button>
              ) : (
                <button
                  type="button"
                  onClick={submit}
                  className="label rounded-full bg-umber px-6 py-3 text-parchment transition-colors hover:bg-obsidian"
                >
                  Request reservation
                </button>
              )}
            </div>
          </footer>
        )}
      </aside>
    </div>
  )
}

function DatesStep({ stay, onChange }: { stay: Stay; onChange: (stay: Stay) => void }) {
  const today = todayISO()
  const nights = nightsBetween(stay.checkIn, stay.checkOut)

  return (
    <div>
      <p className="display text-2xl">When would you like to arrive?</p>
      <div className="mt-8 grid gap-6 sm:grid-cols-2">
        <label className="block">
          <span className="label text-obsidian/45">Arrival</span>
          <input
            type="date"
            aria-label="Arrival date"
            min={today}
            value={stay.checkIn}
            onChange={(event) => onChange({ ...stay, checkIn: event.target.value })}
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="label text-obsidian/45">Departure</span>
          <input
            type="date"
            aria-label="Departure date"
            min={stay.checkIn || today}
            value={stay.checkOut}
            onChange={(event) => onChange({ ...stay, checkOut: event.target.value })}
            className={inputClass}
          />
        </label>
      </div>

      <div className="mt-8">
        <span className="label text-obsidian/45">Guests</span>
        <div className="mt-3 flex gap-2">
          {[1, 2, 3, 4].map((count) => (
            <button
              key={count}
              type="button"
              aria-pressed={stay.guests === count}
              onClick={() => onChange({ ...stay, guests: count })}
              className={cn(
                "h-11 w-11 rounded-full border text-sm transition-colors",
                stay.guests === count
                  ? "border-obsidian bg-obsidian text-parchment"
                  : "border-obsidian/25 text-obsidian/70 hover:border-obsidian/60",
              )}
            >
              {count}
            </button>
          ))}
        </div>
      </div>

      <p className="label mt-8 text-obsidian/40">
        {nights > 0 ? `${nights} night${nights === 1 ? "" : "s"}` : "Select both dates"}
      </p>
    </div>
  )
}

function RoomStep({ stay, onChange }: { stay: Stay; onChange: (stay: Stay) => void }) {
  return (
    <div>
      <p className="display text-2xl">Choose your room.</p>
      <div role="radiogroup" aria-label="Room" className="mt-8">
        {rooms.map((item) => {
          const active = stay.roomId === item.id
          return (
            <button
              key={item.id}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange({ ...stay, roomId: item.id })}
              className={cn(
                "flex w-full items-baseline justify-between gap-4 border-b border-obsidian/15 py-4 text-left transition-colors",
                active ? "text-obsidian" : "text-obsidian/55 hover:text-obsidian",
              )}
            >
              <span className="flex items-baseline gap-3">
                <span
                  className={cn(
                    "h-2 w-2 rounded-full border",
                    active ? "border-umber bg-umber" : "border-obsidian/30",
                  )}
                />
                <span className="display text-xl">{item.name}</span>
              </span>
              <span className="label whitespace-nowrap">{currency.format(item.price)} / night</span>
            </button>
          )
        })}
      </div>
      <p className="mt-8 text-sm text-obsidian/55">
        Rates include breakfast and the evening table. Local taxes are added at confirmation.
      </p>
    </div>
  )
}

function GuestStep({ guest, onChange }: { guest: Guest; onChange: (guest: Guest) => void }) {
  return (
    <div>
      <p className="display text-2xl">Who is coming?</p>
      <div className="mt-8 space-y-7">
        <label className="block">
          <span className="label text-obsidian/45">Name</span>
          <input
            type="text"
            value={guest.name}
            onChange={(event) => onChange({ ...guest, name: event.target.value })}
            autoComplete="name"
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="label text-obsidian/45">Email</span>
          <input
            type="email"
            value={guest.email}
            onChange={(event) => onChange({ ...guest, email: event.target.value })}
            autoComplete="email"
            className={inputClass}
          />
        </label>
        <label className="block">
          <span className="label text-obsidian/45">Anything the kitchen should know</span>
          <textarea
            rows={3}
            value={guest.notes}
            onChange={(event) => onChange({ ...guest, notes: event.target.value })}
            className="mt-2 w-full resize-none border-0 border-b border-obsidian/25 bg-transparent pb-2 text-base focus:border-obsidian focus:outline-none"
          />
        </label>
      </div>
    </div>
  )
}

function ReviewStep({
  room,
  stay,
  nights,
  total,
  guest,
}: {
  room: Room | null
  stay: Stay
  nights: number
  total: number
  guest: Guest
}) {
  return (
    <div>
      <p className="display text-2xl">One last look.</p>
      <dl className="mt-8 border-t border-obsidian/15">
        <Row label="Arrival" value={formatStayDate(stay.checkIn)} />
        <Row label="Departure" value={formatStayDate(stay.checkOut)} />
        <Row label="Nights" value={String(nights)} />
        <Row label="Room" value={room?.name ?? "—"} />
        <Row label="Guests" value={String(stay.guests)} />
        <Row label="Name" value={guest.name} />
        <Row label="Email" value={guest.email} />
        <Row label="Total" value={currency.format(total)} strong />
      </dl>
      <p className="mt-6 text-sm text-obsidian/55">
        This sends a request, not a charge. We reply by email within a day to confirm the room and
        take the details.
      </p>
    </div>
  )
}

function Confirmation({
  reference,
  room,
  stay,
  nights,
  total,
  guest,
}: {
  reference: string
  room: Room | null
  stay: Stay
  nights: number
  total: number
  guest: Guest
}) {
  return (
    <div>
      <p className="display text-2xl">Thank you, {guest.name.split(" ")[0] || "friend"}.</p>
      <p className="mt-4 max-w-sm text-obsidian/65">
        Your request is in the book. We will write to {guest.email} within a day to confirm.
      </p>
      <dl className="mt-8 border-t border-obsidian/15">
        <Row label="Reference" value={reference} strong />
        <Row label="Room" value={room?.name ?? "—"} />
        <Row label="Arrival" value={formatStayDate(stay.checkIn)} />
        <Row label="Departure" value={formatStayDate(stay.checkOut)} />
        <Row label="Nights" value={String(nights)} />
        <Row label="Total" value={currency.format(total)} />
      </dl>
    </div>
  )
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-6 border-b border-obsidian/10 py-3">
      <dt className="label text-obsidian/40">{label}</dt>
      <dd className={cn("text-right", strong ? "font-display text-xl" : "text-obsidian/80")}>{value}</dd>
    </div>
  )
}
