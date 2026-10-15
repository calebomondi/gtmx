import {
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react"
import { useNavigate } from "react-router-dom"
import { AnimatePresence, motion, useReducedMotion } from "motion/react"

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
import { Textarea } from "@/components/ui/textarea"
import { DiscoveryInterruptPicker } from "@/components/interrupt-panel"
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group'
import { COUNTRIES, normalizeCountry } from "@/lib/countries"
import { useDiscovery } from "@/hooks/use-discovery"

import { SourceToggle, type SourceMode } from '@/features/workspace/new/toggle'

/**
 * What the user is offering, asserted rather than inferred. The agent used to
 * classify this from the scraped page over two LLM passes and interrupt when
 * undecided; it now arrives on the session pre-seeded, so this drives the
 * specialist roster and the downstream interview wording directly.
 */
type OfferType = 'product' | 'service'


type NewWorkspaceFormProps = React.ComponentProps<"div"> & {
  isDiscovering: boolean
  setIsDiscovering: React.Dispatch<React.SetStateAction<boolean>>
}

/**
 * Fades copy in when `swapKey` changes. Keying on the value remounts the
 * element, so it re-runs the enter animation. Deliberately no exit variant:
 * the label and its hint are one visual unit, and cross-fading them would
 * briefly render the label with neither word in it.
 */
function SwappingText({
  swapKey,
  className,
  children,
}: {
  swapKey: string
  className?: string
  children: React.ReactNode
}) {
  return (
    <motion.span
      key={swapKey}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className={cn("inline-block", className)}
    >
      {children}
    </motion.span>
  )
}

/**
 * Tracks the natural height of `ref`'s element so a wrapper can animate to it.
 *
 * The wrapper's height is animated, and this reads the *inner* element, whose
 * height is content-driven and therefore independent of the wrapper — so the
 * two can't feed each other into a loop. Motion's `layout` prop is deliberately
 * not used here: it animates size with `scale`, which stretches the input and
 * label text inside the card.
 */
function useMeasuredHeight<T extends HTMLElement>() {
  const ref = useRef<T | null>(null)
  const [height, setHeight] = useState<number | null>(null)

  useLayoutEffect(() => {
    const element = ref.current
    if (!element) return

    const measure = () => {
      const next = element.getBoundingClientRect().height
      // Sub-pixel jitter from the spring would otherwise re-trigger itself.
      setHeight((current) =>
        current === null || Math.abs(current - next) > 0.5 ? next : current,
      )
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return [ref, height] as const
}

// The agent takes a reply this long to "I can't read your website" as the
// offer's description; anything shorter it asks for again.
const MIN_DESCRIPTION_WORDS = 8

const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length

export function NewWorkspaceForm({
  className,
  isDiscovering,
  setIsDiscovering,
  ...props
}: NewWorkspaceFormProps) {
  const [source, setSource] = useState<SourceMode>("website")
  const [offerType, setOfferType] = useState<OfferType>("product")
  // +1 when moving toward "social", -1 toward "website". Drives which way the
  // outgoing fields slide so the motion agrees with the toggle's own direction.
  const [direction, setDirection] = useState(1)
  const [productName, setProductName] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [description, setDescription] = useState("")
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

  // The manual branch has no URL to scrape, so the name matters most either way.
  const nameLabel =
    offerType === "service" ? "Service name" : "Product name"

  // Every remaining piece of product/service-flavoured copy hangs off this one
  // word. All of it stays to a single line on purpose: the name and URL fields
  // sit inside the measured block, so a hint that wrapped to two lines would
  // re-trigger the card's height animation every time the toggle moved.
  const offerNoun = offerType === "service" ? "service" : "product"

  const nameHint =
    source === "social"
      ? "Names your workspace and what you offer."
      : `Which ${offerNoun} should I focus on.`

  // Mirrors the definitions the offer interview uses, so the toggle and the
  // agent are describing the same boundary.
  const offerTypeHint =
    offerType === "service"
      ? "Work performed for a customer."
      : "A thing people buy, own or use."

  // The example has to match the type or it quietly contradicts the toggle
  // above it — a product-shaped sample under "Service" reads as a bug.
  const socialPlaceholder =
    offerType === "service"
      ? "e.g. We help outdoor retailers cut inventory waste."
      : "e.g. We make analytics dashboards for outdoor retailers."

  const isFormReady = useMemo(() => {
    if (productName.trim().length === 0) return false

    return source === "website"
      ? websiteUrl.trim().length > 0 && targetGeo.length > 0
      : description.trim().length > 0 && targetGeo.length > 0
  }, [productName, websiteUrl, description, targetGeo, source])

  // Resuming after an unreadable URL takes either a corrected URL or a
  // description long enough for the agent to work from.
  const clarifyReady = useMemo(
    () =>
      source === "website"
        ? websiteUrl.trim().length > 0
        : wordCount(description) >= MIN_DESCRIPTION_WORDS,
    [source, websiteUrl, description],
  )

  const handleSourceChange = (next: SourceMode) => {
    setDirection(next === "social" ? 1 : -1)
    setSource(next)
  }

  const reduceMotion = useReducedMotion()
  const [branchRef, branchHeight] = useMeasuredHeight<HTMLDivElement>()


  // Tuned by feel against the ~230px branch delta, so all the pacing knobs
  // live here rather than being scattered through the JSX.
  //
  // A tween, not a spring: a 230px change is far enough that a spring's
  // settling time is a side effect of its physics rather than something you
  // can set, and it lands around 280ms — ~820px/sec, which reads as a snap no
  // matter how it's tuned. The long tail of this ease-out curve is what makes
  // the movement look deliberate.
  const EASE_OUT = [0.22, 1, 0.36, 1] as const
  const DURATION = 0.42

  // One duration, one curve, staggered on purpose. When these were independent
  // they each settled 40-120ms apart, so the box, the content, the label and
  // the note all landed at different moments and read as separate events
  // instead of a single gesture.
  const heightTransition = reduceMotion
    ? { duration: 0 }
    : { duration: DURATION, ease: EASE_OUT }

  // The box leads, the content follows just behind its leading edge, and the
  // outgoing content clears out fast so it isn't sitting in the way. Transitions
  // ride on the variants because `enter` and `exit` need different ones.
  const branchVariants = {
    enter: (dir: number) => ({
      opacity: 0,
      x: reduceMotion ? 0 : dir * 20,
      transition: reduceMotion
        ? { duration: 0 }
        : { duration: DURATION, ease: EASE_OUT, delay: 0.08 },
    }),
    center: { opacity: 1, x: 0 },
    exit: (dir: number) => ({
      opacity: 0,
      x: reduceMotion ? 0 : -dir * 20,
      transition: reduceMotion
        ? { duration: 0 }
        : { duration: 0.18, ease: "easeIn" as const },
    }),
  }

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
      if (clarifyReady) answer(source === "social" ? description.trim() : websiteUrl.trim())
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
      product_url: source === 'social' ? '' : websiteUrl,
      offer_description: source === 'social' ? description.trim() : undefined,
      offer_type: offerType,
      source: source === 'social' ? 'manual' : 'website',
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
          <div className="p-6 md:p-8">
            <form  onSubmit={handleSubmit}>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="text-xl font-bold">Create A Workspace</h1>
                <p className="text-balance text-muted-foreground">
                  This workspace will be dedicated to the product or service you pick below.
                </p>
              </div>

              <SourceToggle
                value={source}
                onValueChange={handleSourceChange}
                disabled={isDiscovering}
              />

              <FieldGroup>
                {/* The name field and the source-specific fields are one
                    measured block: switching source changes both the branch
                    height and, via the swapping label, possibly the hint's line
                    count. Measuring them together animates the difference in a
                    single move. The block deliberately stops above Target Geo —
                    the multiselect's country dropdown is `absolute` with no
                    portal, and the `overflow-hidden` needed to clip this
                    transition would cut it off at the card edge. */}
                <motion.div
                  initial={false}
                  animate={{ height: branchHeight ?? "auto" }}
                  transition={heightTransition}
                  className="overflow-hidden"
                >
                  {/* `gap-5` mirrors FieldGroup's own rhythm, which the
                      wrapper now sits between and would otherwise double up. */}
                  <div ref={branchRef} className="flex max-h-[60vh] flex-col gap-5 overflow-y-auto">
                    <div className='flex flex-col gap-2 items-start justify-start'>
                      <p className="text-foreground font-medium">What are you offering?</p>
                      {/* Kept at the group's intrinsic width rather than stretched
                          to match SourceToggle above: this is an assertion about
                          the thing, not a mode switch between two input shapes, so
                          it reads as an inline answer rather than a choice.

                          Deliberately the plain group, not motion-toggle-group.
                          That wrapper suppresses the button's own pressed
                          background via `data-pressed:bg-transparent`, but
                          toggleVariants paints the pressed state with
                          `aria-pressed:bg-muted` — different variants, so twMerge
                          keeps both and the winner falls out of Tailwind's
                          variant sort order rather than intent. One background
                          mechanism here: the button fills itself, padding and
                          all, and `spacing={0}`'s first/last corner treatment
                          still applies.

                          `multiple` defaults to false, so this is single-select
                          without a `type` prop — base-ui has no such prop, and
                          passing one is silently ignored. */}
                      <ToggleGroup
                        value={[offerType]}
                        onValueChange={(next) => {
                          const [picked] = next
                          if (picked && !isDiscovering && !clarifyUrl) setOfferType(picked as OfferType)
                        }}
                        variant='outline'
                        size='lg'
                        spacing={0}
                        disabled={isDiscovering || clarifyUrl}
                      >
                        {/* Only the padding is overridden. Height and type come
                            from `size='lg'`; re-declaring them here is how the
                            button and its pressed background end up disagreeing
                            about how tall the control is. */}
                        <ToggleGroupItem value='product' className='px-4' disabled={isDiscovering || clarifyUrl}>
                          Product
                        </ToggleGroupItem>
                        <ToggleGroupItem value='service' className='px-4' disabled={isDiscovering || clarifyUrl}>
                          Service
                        </ToggleGroupItem>
                      </ToggleGroup>

                      {/* The agent's own definitions, so the two words mean the
                          same thing here as they do downstream. A wrong pick
                          silently changes the specialist roster, which is why
                          this line earns its space. Reserved like SourceToggle's
                          so the card doesn't jump when it swaps. */}
                      <p className="min-h-4 text-xs text-muted-foreground">
                        <SwappingText swapKey={offerTypeHint}>{offerTypeHint}</SwappingText>
                      </p>
                    </div>

                    <Field>
                      <FieldLabel htmlFor="product-name">
                        {/* Keyed on the rendered string, not on `source`. Both
                            swaps can change this text at once (flipping source
                            with service selected), and the social rows are
                            identical for both offer types — keying on `source`
                            alone would leave those not re-animating. */}
                        <SwappingText swapKey={nameLabel}>{nameLabel}</SwappingText>{" "}
                        <span className="text-[var(--destructive)]">*</span>
                      </FieldLabel>
                      <FieldDescription>
                        {/* Keyed on the rendered string for the same reason as
                            the label above: keying on `source` alone would leave
                            this not re-animating when the offer type changes,
                            and would double-fade the social string, which is
                            identical for both types. */}
                        <SwappingText swapKey={nameHint}>{nameHint}</SwappingText>
                      </FieldDescription>
                      <Input
                        id="product-name"
                        value={productName}
                        onChange={(event) => setProductName(event.target.value)}
                        placeholder="e.g. Acme"
                        required
                        disabled={isDiscovering || clarifyUrl}
                      />
                    </Field>

                    <AnimatePresence
                      mode="popLayout"
                      initial={false}
                      custom={direction}
                    >
                      <motion.div
                        key={source}
                        custom={direction}
                        variants={branchVariants}
                        initial="enter"
                        animate="center"
                        exit="exit"
                        className="flex flex-col gap-5"
                      >
                        {source === "website" ? (
                          <Field>
                            <FieldLabel htmlFor="website-url">
                              Website URL <span className="text-[var(--destructive)]">*</span>
                            </FieldLabel>
                            <FieldDescription>
                              {clarifyUrl
                                ? "We couldn't read this page. Fix the URL, or choose No Website and describe it instead."
                                : `The ${offerNoun} page`}
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
                        ) : (
                          <>
                            <Field>
                              <FieldLabel htmlFor="business-description">
                                What does the {offerNoun} do?{" "}
                                <span className="text-[var(--destructive)]">*</span>
                              </FieldLabel>
                              <FieldDescription>
                                {clarifyUrl
                                  ? `We couldn't read your website, so this is my only source. Say what it is, who it's for and what it does, in at least ${MIN_DESCRIPTION_WORDS} words.`
                                  : "Describe it explicitly — what it is and what it does. A couple of sentences is enough, but be specific: this is my only source."}
                              </FieldDescription>
                              <Textarea
                                id="business-description"
                                value={description}
                                onChange={(event) => setDescription(event.target.value)}
                                placeholder={socialPlaceholder}
                                // Fixed rather than the base `field-sizing-content`: the textarea
                                // sits inside the measured block, so auto-growing while typing
                                // would spring the whole card on every line and move the button
                                // out from under the cursor.
                                field-sizing-fixed
                                rows={4}
                                className="max-h-48 overflow-y-auto"
                                required
                                disabled={isDiscovering && !clarifyUrl}
                              />
                            </Field>
                          </>
                        )}
                      </motion.div>
                    </AnimatePresence>
                  </div>
                </motion.div>

                <Field className="">
                  {/* No htmlFor: the multiselect renders a trigger button plus a
                      cmdk input, so there is no element with a stable id to
                      point at. `commandProps.label` carries the accessible name
                      instead. */}
                  <FieldLabel>
                    Target Geo <span className="text-[var(--destructive)]">*</span>
                  </FieldLabel>
                  <FieldDescription>
                    {offerType === "service"
                      ? "Where you want to offer this service"
                      : "Where you target to sell this product"}
                  </FieldDescription>
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
                  <div className="flex flex-col gap-2">
                    <Button
                      type="submit"
                      disabled={
                        clarifyUrl
                          ? !clarifyReady
                          : !isFormReady || isDiscovering
                      }
                      className={`bg-[#FEA853] ${isDiscovering ? 'cursor-not-allowed' : 'cursor-pointer'}`}
                    >
                      {clarifyUrl
                        ? source === "website" ? "Retry with this URL" : "Continue with this description"
                        : isDiscovering
                        ? "Started workspace creation..."
                        : "Create Workspace"}
                    </Button>

                    {/* Lives below the measured block, so it animates its own
                        height rather than relying on the wrapper. */}
                  </div>
                </Field>
              </FieldGroup>
            </form>
          </div>
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
            {isDiscovering && (select || confirm) && (
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
                ? `Finalizing ${(selectedProduct ?? productName) || `your ${offerNoun}`} understanding`
                : `Discovering ${(selectedProduct ?? productName) || `your ${offerNoun}`} ...`}
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