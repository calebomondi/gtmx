import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import { cn } from "cn"

import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import type { Option } from "@/components/ui/multi-select"
import MultipleSelector from "@/components/ui/multi-select"
import { Separator } from "@/components/ui/separator"
import { DiscoveryInterruptPicker } from "@/components/interrupt-panel"
import { COUNTRIES, normalizeCountry } from "@/lib/countries"
import { useDiscovery } from "@/hooks/use-discovery"

type NewWorkspaceFormProps = React.ComponentProps<"div"> & {
  isDiscovering: boolean
  setIsDiscovering: React.Dispatch<React.SetStateAction<boolean>>
}

export function NewWorkspaceForm({
  className,
  isDiscovering,
  setIsDiscovering,
  ...props
}: NewWorkspaceFormProps) {
  const [productName, setProductName] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [targetGeo, setTargetGeo] = useState<Option[]>([])
  const [selectedProduct, setSelectedProduct] = useState<string | null>(null)
  const [confirmed, setConfirmed] = useState(false)
  const navigatedRef = useRef(false)

  const navigate = useNavigate()
  const {
    stage,
    currentInterrupt,
    workspaceId,
    error,
    start,
    answer,
    reset,
  } = useDiscovery()

  const awaiting = stage === "awaiting_input"
  const select =
    awaiting &&
    currentInterrupt?.interrupt_type === "offer_name_mismatch"
  const confirm =
    awaiting &&
    currentInterrupt?.interrupt_type ===
      "product_service_description_confirmation"
  const clarifyUrl =
    awaiting && currentInterrupt?.interrupt_type === "url_unscrappable"
  const chooseType =
    awaiting &&
    currentInterrupt?.interrupt_type === "offer_type_clarification"

  const isFormReady = useMemo(
    () => productName.trim().length > 0 && websiteUrl.trim().length > 0,
    [productName, websiteUrl],
  )

  useEffect(() => {
    if (clarifyUrl) {
      // An unscrappable URL is fixed in place: collapse back to the
      // single-column form so the user can correct the exact field they
      // filled in. Submitting resumes the interrupted run with the corrected
      // URL (answer) instead of starting a new discovery.
      setIsDiscovering(false)
    } else if (
      stage === "connecting" ||
      stage === "awaiting_input" ||
      stage === "running"
    ) {
      setIsDiscovering(true)
    } else if (
      stage === "idle" ||
      stage === "completed" ||
      stage === "error"
    ) {
      setIsDiscovering(false)
    }
  }, [stage, clarifyUrl, setIsDiscovering])

  // The workspace exists as soon as the discovery phase finishes — jump into
  // it while the remaining phases keep streaming for the stepper.
  useEffect(() => {
    if (workspaceId && !navigatedRef.current) {
      navigatedRef.current = true
      navigate(`/workspace/${workspaceId}`, { replace: true })
    }
  }, [workspaceId, navigate])

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()

    if (clarifyUrl) {
      const trimmed = websiteUrl.trim()
      if (trimmed) answer(trimmed)
      return
    }

    if (!isFormReady || isDiscovering) {
      return
    }

    setIsDiscovering(true)
    setSelectedProduct(null)
    setConfirmed(false)
    void start({
      product_name: productName,
      product_url: websiteUrl,
      target_geo:
        targetGeo.length > 0
          ? targetGeo.map((option) => normalizeCountry(option.value))
          : undefined,
    })
  }

  return (
    <div className={cn("flex flex-col", className)} {...props}>
      {/* overflow-visible, not the default: the multiselect renders its country
          dropdown as an `absolute` element inside its own DOM (no portal), and
          Card hardcodes overflow-hidden in its base classes to clip to
          rounded-xl. Anything positioned would get cut off at the card edge.
          The only child that paints a background clips its own corners below. */}
      <Card className="overflow-visible p-0 shadow-lg">
        <CardContent className={cn("grid p-0", isDiscovering && "md:grid-cols-2")}>
          <form className="p-6 md:p-8" onSubmit={handleSubmit}>
            <FieldGroup>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="text-xl font-bold">Create A Workspace</h1>
                <p className="text-balance text-muted-foreground">
                  This workspace will be dedicated to the product or service you provide information for.
                </p>
              </div>

              <Field>
                <FieldLabel htmlFor="product-name">
                  Product/service name <span className="text-[var(--destructive)]">*</span>
                </FieldLabel>
                <FieldDescription>Helps me know which product or service to focus on.</FieldDescription>
                <Input
                  id="product-name"
                  value={productName}
                  onChange={(event) => setProductName(event.target.value)}
                  placeholder="e.g. Acme"
                  required
                  disabled={isDiscovering || clarifyUrl}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="website-url">
                  Website URL <span className="text-[var(--destructive)]">*</span>
                </FieldLabel>
                <FieldDescription>
                  {clarifyUrl
                    ? "We couldn't fetch this page. Fix the URL to resume — everything already gathered is kept."
                    : "The product/service page"}
                </FieldDescription>
                <Input
                  id="website-url"
                  value={websiteUrl}
                  onChange={(event) => setWebsiteUrl(event.target.value)}
                  placeholder="https://example.com"
                  required
                  disabled={isDiscovering && !clarifyUrl}
                />
              </Field>

              <Field className="">
                {/* No htmlFor: the multiselect renders a trigger button plus a
                    cmdk input, so there is no element with a stable id to
                    point at. `commandProps.label` carries the accessible name
                    instead. */}
                <FieldLabel>
                  Target Geo <span className="text-xs">(optional)</span>
                </FieldLabel>
                <FieldDescription>Leave empty for me to decide</FieldDescription>
                <MultipleSelector
                  value={targetGeo}
                  onChange={setTargetGeo}
                  defaultOptions={COUNTRIES}
                  commandProps={{ label: "Select target markets" }}
                  placeholder="Select target markets"
                  creatable
                  hideClearAllButton
                  hidePlaceholderWhenSelected
                  emptyIndicator={
                    <p className="text-center text-sm">No results found</p>
                  }
                  className="w-full"
                  disabled={isDiscovering || clarifyUrl}
                />
              </Field>

              <Field>
                <Button
                  type="submit"
                  disabled={
                    clarifyUrl
                      ? !websiteUrl.trim()
                      : !isFormReady || isDiscovering
                  }
                  className={`bg-[#FEA853] ${isDiscovering ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                >
                  {clarifyUrl
                    ? "Retry with this URL"
                    : isDiscovering
                    ? "Started workspace creation..."
                    : "Create Workspace"}
                </Button>
              </Field>
            </FieldGroup>
          </form>
          <div
            className={cn(
              "relative bg-muted flex-col gap-3 overflow-hidden md:rounded-e-xl transition-all duration-300 ease-out",
              isDiscovering
                ? "flex opacity-100 scale-100 md:justify-center md:items-center"
                : "hidden opacity-0 scale-95",
            )}
          >
            {select && currentInterrupt && (
              <DiscoveryInterruptPicker
                interrupt={currentInterrupt}
                fallbackProductName={productName}
                fallbackUrl={websiteUrl}
                onAnswer={(value) => {
                  const candidates = currentInterrupt.product_candidates ?? []
                  const chosen = /^\d+$/.test(value)
                    ? candidates[Number(value) - 1] ?? null
                    : value
                  if (chosen) setSelectedProduct(chosen)
                  answer(value)
                }}
              />
            )}
            {confirm && currentInterrupt && (
              <DiscoveryInterruptPicker
                interrupt={currentInterrupt}
                fallbackProductName={selectedProduct ?? productName}
                fallbackUrl={websiteUrl}
                onAnswer={(value) => {
                  if (/^yes$/i.test(value.trim())) setConfirmed(true)
                  answer(value)
                }}
              />
            )}
            {chooseType && currentInterrupt && (
              <DiscoveryInterruptPicker
                interrupt={currentInterrupt}
                fallbackProductName={selectedProduct ?? productName}
                fallbackUrl={websiteUrl}
                onAnswer={answer}
              />
            )}
            {isDiscovering && (select || confirm || chooseType) && (
              <Separator />
            )}
            <div className="grid place-items-center p-2">
              <div className="loader">
                <svg viewBox="0 0 80 80">
                  <rect height="64" width="64" y="8" x="8"></rect>
                </svg>
              </div>
            </div>
            <span className="max-w-full text-balance text-muted-foreground px-4 pb-2 text-center">
              {stage === "awaiting_input"
                ? "Waiting for your answer..."
                : confirmed
                ? `Finalizing ${(selectedProduct ?? productName) || "your product/service"} understanding`
                : `Discovering ${(selectedProduct ?? productName) || "your product/service"} ...`}
            </span>
          </div>
        </CardContent>
      </Card>
      {stage === "error" && error && (
        <div
          role="alert"
          className="mt-3 flex items-center justify-between gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive"
        >
          <span>{error}</span>
          <Button
            variant="ghost"
            size="sm"
            className="cursor-pointer text-inherit"
            onClick={reset}
          >
            Dismiss
          </Button>
        </div>
      )}
    </div>
  )
}