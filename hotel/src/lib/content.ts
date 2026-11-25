export type RoomId = "salt" | "stone" | "linen"

export type Stay = {
  checkIn: string
  checkOut: string
  guests: number
  roomId: RoomId | null
}

export type Room = {
  id: RoomId
  numeral: string
  name: string
  tagline: string
  image: string
  price: number
  specs: { label: string; value: string }[]
}

export type GalleryItem = {
  caption: string
  note: string
  image: string
}

const unsplash = (id: string, width = 1400) =>
  `https://images.unsplash.com/photo-${id}?auto=format&fit=crop&w=${width}&q=80`

export const images = {
  hero: unsplash("1600585154340-be6161a56a0c", 2000),
  house: unsplash("1511818966892-d7d671e672a2", 1200),
  night: unsplash("1566073771259-6a8506099945", 2000),
}

export const rooms: Room[] = [
  {
    id: "salt",
    numeral: "I",
    name: "The Salt Room",
    tagline: "Sea-facing, first floor of the old wing, above the jetty wall.",
    image: unsplash("1618773928121-c32242e63f39"),
    price: 420,
    specs: [
      { label: "Surface", value: "42 m², one bed" },
      { label: "Aspect", value: "East, over the water" },
      { label: "Scent", value: "Cedar, salt, cold stone" },
      { label: "Sound", value: "The tide, twice a day" },
      { label: "Bath", value: "Hand-cut coral rag" },
    ],
  },
  {
    id: "stone",
    numeral: "II",
    name: "The Stone Suite",
    tagline: "A courtyard suite behind a wall of cut coral, cool at noon.",
    image: unsplash("1582719478250-c89cae4dc85b"),
    price: 680,
    specs: [
      { label: "Surface", value: "68 m², two rooms" },
      { label: "Aspect", value: "South, onto the lime courtyard" },
      { label: "Scent", value: "Fig leaf, wet plaster" },
      { label: "Sound", value: "Rain on the roof tiles" },
      { label: "Bath", value: "A sunken basin of dark stone" },
    ],
  },
  {
    id: "linen",
    numeral: "III",
    name: "The Linen Loft",
    tagline: "Under the roof, shutters on three sides, the evening arriving early.",
    image: unsplash("1590490360182-c33d57733427"),
    price: 540,
    specs: [
      { label: "Surface", value: "55 m², one bed, one daybed" },
      { label: "Aspect", value: "West, into the evening" },
      { label: "Scent", value: "Sun-warmed cotton" },
      { label: "Sound", value: "Wind through the shutters" },
      { label: "Bath", value: "Cold water, poured by hand" },
    ],
  },
]

export const gallery: GalleryItem[] = [
  {
    caption: "Sourdough, day two",
    note: "Stone-milled, sea-salted",
    image: unsplash("1509440159596-0249088772ff", 1200),
  },
  {
    caption: "The terrace, laid for eight",
    note: "Sea on three sides",
    image: unsplash("1559339352-11d035aa65de", 1200),
  },
  {
    caption: "Flowers for the hall",
    note: "Cut at dawn, changed daily",
    image: unsplash("1594026112284-02bb6f3352fe", 1200),
  },
  {
    caption: "Lunch, in one bowl",
    note: "Whatever the boats brought",
    image: unsplash("1504674900247-0877df9cc836", 1200),
  },
  {
    caption: "Suite II, at dusk",
    note: "Linen, and the last of the light",
    image: unsplash("1540518614846-7eded433c457", 1200),
  },
  {
    caption: "The last plate",
    note: "Between services",
    image: unsplash("1414235077428-338989a2e8c0", 1200),
  },
]

export const houseNotes = [
  {
    label: "Arrival",
    body: "Boats from Manda cross on the tide. Tell us the hour and someone will be waiting at the jetty with a light.",
  },
  {
    label: "The Table",
    body: "Dinner is one seating, at eight. Tell the kitchen what you cannot eat, and nothing else. Breakfast runs until it stops.",
  },
  {
    label: "Coordinates",
    body: "2°16′S 40°54′E — Lamu Old Town, Kenya. Nine rooms, one courtyard, no lifts, no hurry.",
  },
]

export const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
})

export function nightsBetween(checkIn: string, checkOut: string): number {
  if (!checkIn || !checkOut) return 0
  const start = new Date(`${checkIn}T00:00:00`)
  const end = new Date(`${checkOut}T00:00:00`)
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) return 0
  return Math.round((end.getTime() - start.getTime()) / 86_400_000)
}

export function todayISO(): string {
  const now = new Date()
  const offset = now.getTimezoneOffset() * 60_000
  return new Date(now.getTime() - offset).toISOString().slice(0, 10)
}

export function formatStayDate(value: string): string {
  if (!value) return "—"
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
  })
}
