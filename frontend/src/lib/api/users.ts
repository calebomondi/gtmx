import { apiFetch } from "./http"

export interface CurrentUser {
  id: string
  name: string | null
  email: string | null
  avatar_url: string | null
}

let currentUserPromise: Promise<CurrentUser> | null = null

export function clearCurrentUserCache(): void {
  currentUserPromise = null
}

export function getCurrentUser(): Promise<CurrentUser> {
  currentUserPromise ??= apiFetch<CurrentUser>("/api/v1/users/me").catch((err) => {
    // Never memoize a failure: a transient 401/500 would otherwise poison the
    // cache for the rest of the page session and workspaces/projects would
    // look empty even after the server recovers.
    currentUserPromise = null
    throw err
  })
  return currentUserPromise
}
