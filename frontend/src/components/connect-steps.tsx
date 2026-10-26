import { CONNECT_STEPS, PLATFORM_LABEL, type Platform } from "@/lib/platforms"

/** The steps an app needs from the founder before connecting (Telegram's bot
 * token), numbered; nothing for apps that need none. */
export function ConnectSteps({ platform }: { platform: Platform }) {
  const steps = CONNECT_STEPS[platform]
  if (!steps) return null
  return (
    <div className="rounded-lg border bg-muted/40 p-3 text-sm">
      <p className="mb-2 font-medium">Before you connect {PLATFORM_LABEL[platform]}</p>
      <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
        {steps.map((step) => <li key={step}>{step}</li>)}
      </ol>
    </div>
  )
}
