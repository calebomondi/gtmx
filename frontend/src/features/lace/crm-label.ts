import type { LaceAccountDto } from "@/lib/api"

const STATUS_LABEL: Record<NonNullable<LaceAccountDto["crm_status"]>, string> = {
  customer: "customer", open_deal: "open deal", lead: "lead", known: "on file",
}

/** "In your CRM · open deal, Negotiation": where a lead stands in the founder's CRM. */
export function crmLabel(account: LaceAccountDto): string | null {
  if (!account.crm_status) return null
  const stage = account.crm_stage && account.crm_stage.toLowerCase() !== STATUS_LABEL[account.crm_status]
    ? `, ${account.crm_stage}` : ""
  return `In your CRM · ${STATUS_LABEL[account.crm_status]}${stage}`
}
