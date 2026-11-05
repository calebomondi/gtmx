/** The lists the Lace's page keeps loaded from the server. */
export type ChatList = "lace" | "messages" | "facts" | "competitors" | "accounts" | "outreach" | "contacts"

export const EVERY_LIST: readonly ChatList[] = ["lace", "messages", "facts", "competitors", "accounts", "outreach", "contacts"]

// A job reports back in the chat, so the messages (and the Lace's mood) come
// along with whatever it changed.
const REPORTED: readonly ChatList[] = ["lace", "messages"]

/** What each background job changes when it ends. */
const JOB_CHANGES: Record<string, readonly ChatList[]> = {
  lace_competitors: ["competitors"],
  lace_monitor: ["competitors"],
  lace_accounts: ["accounts", "contacts"],
  lace_contacts: ["accounts", "contacts"],
  lace_icp: ["facts", "accounts"],
  lace_drafts: ["outreach", "contacts"],
  lace_reply: ["outreach"],
  lace_opportunities: [],
  lace_listening: ["outreach"],
  lace_refresh: ["facts"],
  lace_comments: [],
  lace_regulations: [],
}

/** What each kind of Feed item says changed. */
const ACTIVITY_CHANGES: Record<string, readonly ChatList[]> = {
  reply_received: ["outreach"],
  drafts_ready: ["outreach"],
  message_sent: ["outreach"],
  competitors_found: ["competitors"],
  competitor_moves: ["competitors"],
  competitor_saved: ["competitors"],
  accounts_found: ["accounts", "contacts"],
  contacts_found: ["accounts", "contacts"],
  account_saved: ["accounts"],
  opportunities_found: [],
  opportunity_saved: [],
  comments_read: [],
  regulations_found: [],
  bill_moved: [],
}

/** The lists to load again after jobs of `endedJobs` kinds ended and/or a Feed
 * item of `newActivity` kind arrived: only what they change, or every list
 * for a kind this page doesn't know. */
export function listsToReload(endedJobs: readonly string[], newActivity: string | null): ChatList[] {
  const kinds = [...endedJobs.map((kind) => JOB_CHANGES[kind]),
                 ...(newActivity === null ? [] : [ACTIVITY_CHANGES[newActivity]])]
  if (kinds.some((changes) => changes === undefined)) return [...EVERY_LIST]
  return [...new Set([...REPORTED, ...kinds.flatMap((changes) => changes ?? [])])]
}
