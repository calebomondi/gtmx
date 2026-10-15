import { useState } from "react"
import { Link } from "react-router-dom"

import { supabase } from "@/lib/supabase"
import { isValidEmail } from "@/lib/validation"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("")
  const [emailTouched, setEmailTouched] = useState(false)
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const emailValid = isValidEmail(email)
  const emailError =
    emailTouched && email.length > 0 && !emailValid
      ? "Enter a valid email address (e.g. name@example.com)."
      : null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEmailTouched(true)
    if (!emailValid) return
    setError(null)
    setBusy(true)
    const { error } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: `${window.location.origin}/auth/callback?next=/auth/update-password`,
    })
    setBusy(false)
    if (error) {
      setError(error.message)
      return
    }
    setSent(true)
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Reset your password</CardTitle>
          <CardDescription>
            Enter your account email and we&apos;ll send you a reset link.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="email">Email</FieldLabel>
                <Input
                  id="email"
                  type="email"
                  placeholder="m@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  onBlur={() => setEmailTouched(true)}
                  disabled={sent}
                  aria-invalid={emailError ? true : undefined}
                  className={
                    emailError ? "border-red-500 focus-visible:ring-red-500" : undefined
                  }
                  required
                />
                {emailError && <p className="text-sm text-red-500">{emailError}</p>}
              </Field>
              {error && <p className="text-sm text-red-500">{error}</p>}
              {sent && (
                <p className="text-sm text-green-500">
                  Check your email for the password reset link.
                </p>
              )}
              <Field>
                <Button type="submit" disabled={busy || !emailValid || sent}>
                  {sent ? "Reset link sent" : busy ? "Sending…" : "Send reset link"}
                </Button>
              </Field>
              <p className="text-center text-sm">
                <Link to="/auth/login" className="underline-offset-4 hover:underline">
                  Back to sign in
                </Link>
              </p>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
