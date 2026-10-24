// The apps a user can connect (via Composio), as every app shows them. Mirrors
// the backend's registry (services/connections.APPS).

import { startConnection, startLaceConnection } from "@/lib/api"

export type Platform =
  | 'gmail' | 'outlook' | 'googlecalendar' | 'linkedin' | 'instagram' | 'facebook' | 'tiktok' | 'x' | 'whatsapp'
  | 'zoho' | 'hubspot' | 'googlesheets' | 'notion' | 'slack' | 'asana' | 'calendly'

export const PLATFORM_LABEL: Record<Platform, string> = {
  gmail: 'Gmail',
  outlook: 'Outlook',
  googlecalendar: 'Google Calendar',
  linkedin: 'LinkedIn',
  instagram: 'Instagram',
  facebook: 'Facebook',
  tiktok: 'TikTok',
  x: 'X',
  whatsapp: 'WhatsApp Business',
  zoho: 'Zoho CRM',
  hubspot: 'HubSpot',
  googlesheets: 'Google Sheets',
  notion: 'Notion',
  slack: 'Slack',
  asana: 'Asana',
  calendly: 'Calendly',
}

/** Empty string means "no icon asset" — the tile renders the name's first letter instead. */
export const PLATFORM_ICON: Record<Platform, string> = {
  gmail: '/gmail.svg',
  outlook: '',
  googlecalendar: '/google-calendar.svg',
  linkedin: '/linkedin.svg',
  instagram: '/instagram.svg',
  facebook: '/facebook.svg',
  tiktok: '/tiktok-mark.svg',
  x: '',
  whatsapp: '/whatsapp.svg',
  zoho: '/zoho.svg',
  hubspot: '/hubspot.svg',
  googlesheets: '/google-sheets.svg',
  notion: '/notion.svg',
  slack: '/slack.svg',
  asana: '/asana.svg',
  calendly: '/calendly.svg',
}

/** Icons drawn in black, inverted on dark themes so they stay visible. */
export const DARK_ICONS: ReadonlySet<Platform> = new Set(['notion'])

export type AppGroup = 'channels' | 'crm' | 'docs' | 'team' | 'meetings'

/** The apps by what a Lace does with them, in display order. */
export const APP_GROUPS: { key: AppGroup; label: string; blurb: string; platforms: Platform[] }[] = [
  { key: 'channels', label: 'Channels', blurb: 'Where your Lace reaches people and reads their replies.',
    platforms: ['gmail', 'outlook', 'linkedin', 'x', 'instagram', 'facebook', 'tiktok', 'whatsapp'] },
  { key: 'crm', label: 'CRM', blurb: 'Your pipeline: who is already a lead, and what your deals add up to.',
    platforms: ['zoho', 'hubspot'] },
  { key: 'docs', label: 'Sheets & docs', blurb: 'Lists to import and export, and pages to read and write.',
    platforms: ['googlesheets', 'notion'] },
  { key: 'team', label: 'Team & tasks', blurb: 'Your brief and alerts where your team works, and follow-ups as tasks.',
    platforms: ['slack', 'asana'] },
  { key: 'meetings', label: 'Meetings', blurb: 'Free slots and booking links for the people who want to talk.',
    platforms: ['googlecalendar', 'calendly'] },
]

/** Every app the user can connect, in display order. */
export const ALL_PLATFORMS: Platform[] = APP_GROUPS.flatMap((group) => group.platforms)

/** Apps a Lace can't use yet: they connect now, and their skills arrive one by one. */
export const COMING_SOON: ReadonlySet<Platform> = new Set([
  'outlook', 'whatsapp', 'zoho', 'hubspot', 'googlesheets', 'notion', 'slack', 'asana', 'calendly',
])

/** Sends the browser to the platform's sign-in (via Composio) for a shared
 * account, which every Lace uses. It comes back to `returnTo` (an app path;
 * the accounts page by default) with ?connected=<platform>. */
export async function beginConnection(platform: Platform, returnTo?: string): Promise<void> {
  const { redirect_url } = await startConnection(platform, returnTo)
  window.location.assign(redirect_url)
}

/** The same, for an account only this Lace uses; it comes back to the Lace. */
export async function beginLaceConnection(laceId: string, platform: Platform): Promise<void> {
  const { redirect_url } = await startLaceConnection(laceId, platform, `/lace/${laceId}`)
  window.location.assign(redirect_url)
}
