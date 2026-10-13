/** The sections of a workspace, as they appear in the URL (`?tab=`). */
export type WorkspaceTab = 'feed' | 'outreach' | 'product' | 'competition' | 'agent'

export const WORKSPACE_TAB_VALUES: WorkspaceTab[] = ['feed', 'outreach', 'product', 'competition', 'agent']

export function isWorkspaceTab(value: string | null): value is WorkspaceTab {
  return value !== null && (WORKSPACE_TAB_VALUES as string[]).includes(value)
}
