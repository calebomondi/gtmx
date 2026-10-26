import { useLocation, useNavigate } from "react-router-dom"

import { sectionFromHash, sectionHash, type LaceSection } from "./lace-activity-actions"

/** Which sub-tab is open, kept in the URL hash so links (from Home, search,
 * an activity) open the right one and Back returns to the last. */
export function useSection<S extends LaceSection>(sections: readonly S[]): [S, (next: S) => void] {
  const { hash } = useLocation()
  const navigate = useNavigate()
  const current = sectionFromHash(hash, sections) ?? sections[0]
  return [current, (next) => navigate({ hash: sectionHash(next) }, { replace: true })]
}
