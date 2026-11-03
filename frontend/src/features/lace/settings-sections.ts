import { Blocks, BookOpen, FileText, MapPin, Newspaper, Radar, Settings2, type LucideIcon } from "lucide-react"

export type SettingsSection = "watch" | "brief" | "apps" | "where" | "knows" | "documents" | "manage"

export interface Section {
  id: SettingsSection
  label: string
  icon: LucideIcon
  /** What the section is for, under its title; none when its content says so itself. */
  about?: (name: string) => string
  /** Admins and the owner change it; members only see it. */
  admins?: boolean
  /** Only the owner sees it. */
  owner?: boolean
}

export const SECTIONS: Section[] = [
  { id: "watch", label: "Keeping watch", icon: Radar, admins: true },
  { id: "brief", label: "Brief", icon: Newspaper, admins: true },
  { id: "apps", label: "Apps & accounts", icon: Blocks, admins: true,
    about: (name) => `The apps ${name} works in. It acts in them only when you approve, and only in the ones switched on here.` },
  { id: "where", label: "Where we operate", icon: MapPin,
    about: (name) => `Where you're registered and operate. ${name} watches the laws that apply there.` },
  { id: "knows", label: "What it knows", icon: BookOpen,
    about: () => "Learned from your site, its research and you. Each fact keeps its source." },
  { id: "documents", label: "Documents", icon: FileText,
    about: (name) => `What you shared with ${name} in the chat. It reads them when they matter.` },
  { id: "manage", label: "Manage", icon: Settings2, owner: true,
    about: (name) => `Archive or delete ${name}.` },
]

/** The section a link asks for (?settings=apps); back from connecting an app, its apps. */
export function sectionFromUrl(search: string): SettingsSection | null {
  const params = new URLSearchParams(search)
  const asked = params.get("settings")
  if (SECTIONS.some((s) => s.id === asked)) return asked as SettingsSection
  if (params.has("connected")) return "apps"
  return params.has("settings") ? "watch" : null
}
