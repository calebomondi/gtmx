import { useEffect, useMemo } from 'react'

import type { Specialist } from '@/components/specialist-avatargroup'
import { ensureInsightsLoaded, useInsights } from '@/lib/insights-store'
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

/** Convert a persisted specialist team into the avatar-group DTOs. */
export function teamToAvatarSpecialists(
  team: SpecialistDto[] | null | undefined,
): Specialist[] {
  if (!team) return []
  return team.map((member, index) => ({
    id: member.domain,
    fallback: initialsFor(member.name),
    tooltip: `${member.name} · ${member.role}`,
    borderClass: SPECIALIST_BORDERS[index % SPECIALIST_BORDERS.length],
  }))
}

/** Specialist avatars for one workspace (lazily fetched via insights). */
export function useWorkspaceSpecialists(workspaceId: string | undefined): Specialist[] {
  const { insights } = useInsights(workspaceId)
  useEffect(() => {
    if (workspaceId) ensureInsightsLoaded(workspaceId)
  }, [workspaceId])
  return useMemo(
    () => teamToAvatarSpecialists(insights?.specialists),
    [insights],
  )
}