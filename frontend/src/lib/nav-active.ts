/**
 * Active-state matching for the app sidebar.
 *
 * The sidebar renders several lists whose entries point at different route
 * shapes: some own an exact path, some own a whole subtree. These helpers keep
 * that knowledge out of the nav components so they only declare a url.
 */

/** Does a sidebar entry point at the route currently on screen? */
export function isNavItemActive(pathname: string, url: string): boolean {
  // "#" placeholders aren't real destinations, so they never read as active.
  if (!url.startsWith("/")) return false
  // The trailing slash keeps /projects-archive from matching /projects.
  return pathname === url || pathname.startsWith(`${url}/`)
}

/**
 * Is this workspace the one on screen? Covers both /workspace/:id and the
 * nested /projects/:project_id/workspace/:id route, but deliberately not the
 * read-only snapshot at /archive/workspace/:id.
 */
export function isWorkspaceActive(pathname: string, id: string): boolean {
  // An archived snapshot has its own route; highlighting the live entry of the
  // same id would point at the wrong thing.
  if (pathname.startsWith("/archive/")) return false
  return (
    pathname === `/workspace/${id}` || pathname.endsWith(`/workspace/${id}`)
  )
}