import { NewWorkspaceForm } from "@/components/new-workspace-form"
import { useState } from "react"
import { useNavigate } from "react-router-dom"

import { useAuth } from "@/lib/auth"
import { Button } from "@/components/ui/button"

export default function NewWorkspace() {
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false)
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  if (!loading && !user) {
    return (
      <div className="flex min-h-svh flex-col items-center justify-center gap-4 bg-muted p-6 md:p-10">
        <p className="text-lg font-medium">Sign in to create a workspace</p>
        <p className="text-sm text-muted-foreground">
          You can browse the app without an account, but creating workspaces
          requires signing in.
        </p>
        <Button onClick={() => navigate("/auth/login")}>Sign in</Button>
      </div>
    )
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center bg-muted p-6 md:p-10">
      <div className={`w-full max-w-md ${isDiscovering ? "md:max-w-4xl" : ""}`}>
        <NewWorkspaceForm
          className=""
          isDiscovering={isDiscovering}
          setIsDiscovering={setIsDiscovering}
        />
      </div>
    </div>
  )
}
