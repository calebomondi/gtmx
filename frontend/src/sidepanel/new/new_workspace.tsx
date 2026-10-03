import { NewWorkspaceForm } from "@/components/new-workspace-form"
import { useState } from "react"

export default function NewWorkspace() {
  const [isDiscovering, setIsDiscovering] = useState<boolean>(false)

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
