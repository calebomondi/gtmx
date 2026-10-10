const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function isValidEmail(value: string): boolean {
  return EMAIL_RE.test(value.trim())
}

export interface PasswordRule {
  label: string
  test: (v: string) => boolean
}

export const PASSWORD_RULES: PasswordRule[] = [
  { label: "at least 6 characters", test: (v) => v.length >= 6 },
  { label: "a lowercase letter", test: (v) => /[a-z]/.test(v) },
  { label: "an uppercase letter", test: (v) => /[A-Z]/.test(v) },
  { label: "a digit", test: (v) => /\d/.test(v) },
  { label: "a symbol", test: (v) => /[^A-Za-z0-9]/.test(v) },
]

export function passwordIssues(value: string): string[] {
  return PASSWORD_RULES.filter((r) => !r.test(value)).map((r) => r.label)
}

export function isValidPassword(value: string): boolean {
  return passwordIssues(value).length === 0
}

/** A same-site path to return to after sign-in, or null. Rejects absolute and
 * protocol-relative URLs ("//evil.com") so `?next=` can't be an open redirect. */
export function safeNextPath(raw: string | null): string | null {
  if (!raw || !raw.startsWith("/") || raw.startsWith("//") || raw.startsWith("/\\")) return null
  return raw
}
