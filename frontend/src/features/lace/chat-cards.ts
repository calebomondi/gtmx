import type { CardBlockDto, LaceAccountDto, LaceOutreachDto } from "@/lib/api"

/** Where a card's item stands now, which decides its buttons. A card is a
 * snapshot; what it shows as done or gone comes from the current data. */
export type CardState =
  | { kind: "competitor"; tracked: boolean }
  | { kind: "account"; account: LaceAccountDto | null }
  | { kind: "opportunity" }
  | { kind: "draft"; message: LaceOutreachDto | null }

export function cardState(card: CardBlockDto, data: {
  competitorIds: ReadonlySet<string>
  accounts: LaceAccountDto[]
  outreach: LaceOutreachDto[]
}): CardState {
  switch (card.kind) {
    case "competitor":
      return { kind: "competitor", tracked: data.competitorIds.has(card.id) }
    case "account":
      return { kind: "account", account: data.accounts.find((a) => a.id === card.id) ?? null }
    case "opportunity":
      return { kind: "opportunity" }
    case "draft":
      return { kind: "draft", message: data.outreach.find((m) => m.id === card.id) ?? null }
  }
}

/** "2 people found", "No one found yet", or nothing until it was searched. */
export function contactsLine(account: LaceAccountDto): string | null {
  const people = account.contacts.filter((c) => c.name).length
  if (people > 0) return `${people} ${people === 1 ? "person" : "people"} to contact`
  if (account.contacts_checked_at) return "No one named found yet"
  return null
}
