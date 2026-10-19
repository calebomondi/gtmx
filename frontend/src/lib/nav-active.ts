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
