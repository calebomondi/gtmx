import type { CardBlockDto, LaceAccountDto, LaceOutreachDto } from "@/lib/api"

/** Where a card's item stands now, which decides its buttons. A card is a
 * snapshot; what it shows as done or gone comes from the current data. */
/** saved: worked from. suggested: waits for the founder. gone: dismissed. */
export type Standing = "saved" | "suggested" | "gone"

export type CardState =
  | { kind: "competitor"; standing: Standing }
  | { kind: "account"; standing: Standing; account: LaceAccountDto | null }
  | { kind: "opportunity" }
  | { kind: "draft"; message: LaceOutreachDto | null }

export function cardState(card: CardBlockDto, data: {
  competitorIds: ReadonlySet<string>
  suggestedCompetitorIds: ReadonlySet<string>
  accounts: LaceAccountDto[]
  suggestedAccounts: LaceAccountDto[]
  outreach: LaceOutreachDto[]
}): CardState {
  switch (card.kind) {
    case "competitor":
      return { kind: "competitor", standing: data.competitorIds.has(card.id) ? "saved"
        : data.suggestedCompetitorIds.has(card.id) ? "suggested" : "gone" }
    case "account": {
      const saved = data.accounts.find((a) => a.id === card.id)
      const suggested = data.suggestedAccounts.find((a) => a.id === card.id)
      return { kind: "account", standing: saved ? "saved" : suggested ? "suggested" : "gone",
               account: saved ?? suggested ?? null }
    }
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
