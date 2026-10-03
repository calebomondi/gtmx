import { useEffect, useMemo } from 'react'

import type { Specialist } from '@/components/specialist-avatargroup'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'
import { useAgentRun } from '@/lib/agent-run-store'
import type { SpecialistDto } from '@/lib/api'

const SPECIALIST_BORDERS = [
  'border-red-500',
  'border-green-500',
  'border-blue-500',
  'border-amber-500',
]

function initialsFor(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase()
}

/** Domains that are acronyms rather than ordinary words. */
const DOMAIN_ACRONYMS: Record<string, string> = { gtm: 'GTM' }

/**
 * "product" -> "Product Specialist". The domain arrives as a raw lowercase
 * literal from the agent, so it needs the same title-casing the rest of the app
 * applies to names -- except for acronyms, which stay uppercase.
 */
function domainLabel(domain: string): string {
  const base =
    DOMAIN_ACRONYMS[domain] ??
    (domain.charAt(0).toUpperCase() + domain.slice(1))
  return `${base} Specialist`
}

/** Convert a persisted specialist team into the avatar-group DTOs. */
export function teamToAvatarSpecialists(
  team: SpecialistDto[] | null | undefined,
): Specialist[] {
  if (!team) return []
  return team.map((member, index) => ({
    id: member.domain,
    fallback: initialsFor(member.name),
    domain: domainLabel(member.domain),
    name: member.name,
    role: member.role,
    borderClass: SPECIALIST_BORDERS[index % SPECIALIST_BORDERS.length],
  }))
}

/**
 * The one place that decides which specialist team a workspace has. The live
 * run's `create_specialists` phase result wins, because it is the freshest
 * answer and is the only one available while the run is still going; the
 * persisted insights are the fallback once the run is over or the user has
 * reloaded the page.
 *
 * Every surface that shows the team (workspace header, agent chat, project hub)
 * reads through here on purpose. They previously disagreed: the header
 * consulted the live run while the agent chat read insights only, so opening
 * the agent tab could show *fewer* avatars than the header right above it.
 */
export function useSpecialistTeam(
  workspaceId: string | undefined,
): SpecialistDto[] | null {
  const { insights } = useInsights(workspaceId)
  const run = useAgentRun()
  // `run.workspaceId` is `string | null`, so an absent `workspaceId` (the
  // legacy `/workspace` route) never matches here and falls through cleanly.
  const live =
    run.workspaceId !== null && run.workspaceId === workspaceId
      ? run.phaseResults.create_specialists
      : undefined
  return live ?? insights?.specialists ?? null
}

/** Specialist avatars for one workspace (lazily fetched via insights). */
export function useWorkspaceSpecialists(workspaceId: string | undefined): Specialist[] {
  useEffect(() => {
    if (workspaceId) ensureInsightsLoaded(workspaceId)
  }, [workspaceId])
  const team = useSpecialistTeam(workspaceId)
  // Keyed on the resolved team rather than on `insights`, so the live-run
  // branch can actually invalidate this instead of being masked by an
  // unchanged insights object.
  return useMemo(() => teamToAvatarSpecialists(team), [team])
}