// The channels a user can connect (via Composio), as every app shows them.

import { startConnection } from "@/lib/api"

export type Platform = 'gmail' | 'googlecalendar' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok' | 'x'

export const PLATFORM_LABEL: Record<Platform, string> = {
  gmail: 'Gmail',
  googlecalendar: 'Google Calendar',
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  facebook: 'Facebook',
  tiktok: 'TikTok',
  x: 'X',
}

/** Empty string means "no icon asset" — the tile renders a glyph instead. */
export const PLATFORM_ICON: Record<Platform, string> = {
  gmail: '/gmail.svg',
  googlecalendar: '/google-calendar.svg',
  linkedin: '/linkedin.svg',
  instagram: '/instagram.svg',
  facebook: '/facebook.svg',
  tiktok: '/tiktok.svg',
  x: '',
}

/** Every channel the app can connect, in display order. */
export const ALL_PLATFORMS: Platform[] = ['gmail', 'googlecalendar', 'linkedin', 'instagram', 'facebook', 'tiktok', 'x']

/** Sends the browser to the platform's sign-in (via Composio). It comes back
 * to `returnTo` (an app path; the accounts page by default) with
 * ?connected=<platform>. */
export async function beginConnection(platform: Platform, returnTo?: string): Promise<void> {
  const { redirect_url } = await startConnection(platform, returnTo)
  window.location.assign(redirect_url)
}
