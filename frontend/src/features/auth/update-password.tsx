import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { supabase } from "@/lib/supabase"
import { passwordIssues } from "@/lib/validation"
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

export default function UpdatePasswordPage() {
  const navigate = useNavigate()
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [passwordTouched, setPasswordTouched] = useState(false)
  const [confirmTouched, setConfirmTouched] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const issues = passwordIssues(password)
  const passwordValid = issues.length === 0
  const passwordError =
    passwordTouched && password.length > 0 && !passwordValid
      ? `Password needs: ${issues.join(", ")}.`
      : null
  const confirmError =
    confirmTouched && confirm.length > 0 && confirm !== password
      ? "Passwords do not match."
      : null
  const formValid = passwordValid && confirm === password && confirm.length > 0

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setPasswordTouched(true)
    setConfirmTouched(true)
    if (!formValid) return
    setError(null)
    setBusy(true)
    const { error } = await supabase.auth.updateUser({ password })
    setBusy(false)
    if (error) {
      setError(error.message)
      return
    }
    navigate("/feed", { replace: true })
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-6 bg-muted p-6 md:p-10">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <CardTitle className="text-xl">Set a new password</CardTitle>
          <CardDescription>Enter and confirm your new password.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit}>
            <FieldGroup>
              <Field>
                <FieldLabel htmlFor="password">New password</FieldLabel>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  onBlur={() => setPasswordTouched(true)}
                  aria-invalid={passwordError ? true : undefined}
                  className={
                    passwordError ? "border-red-500 focus-visible:ring-red-500" : undefined
                  }
                  required
                />
                {passwordError && (
                  <p className="text-sm text-red-500">{passwordError}</p>
                )}
              </Field>
              <Field>
                <FieldLabel htmlFor="confirm">Confirm password</FieldLabel>
                <Input
                  id="confirm"
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  onBlur={() => setConfirmTouched(true)}
                  aria-invalid={confirmError ? true : undefined}
                  className={
                    confirmError ? "border-red-500 focus-visible:ring-red-500" : undefined
                  }
                  required
                />
                {confirmError && (
                  <p className="text-sm text-red-500">{confirmError}</p>
                )}
              </Field>
              {error && <p className="text-sm text-red-500">{error}</p>}
              <Field>
                <Button type="submit" disabled={busy || !formValid}>
                  {busy ? "Updating…" : "Update password"}
                </Button>
              </Field>
            </FieldGroup>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
