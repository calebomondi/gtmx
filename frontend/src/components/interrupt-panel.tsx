import { useState } from "react"

import { cn } from "cn"

import { Button } from "@/components/ui/button"
import {
  ButtonGroup,
  ButtonGroupSeparator,
} from "@/components/ui/button-group"
import { Input } from "@/components/ui/input"
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { ArrowUpRight, CornerDownRight, X } from "lucide-react"
import type { DiscoveryInterruptFrame } from "@/lib/api"

/**
 * Shared renderer for every discovery interrupt type.
 *
 * The four intake questions select/correct/clarify what the agent scraped.
 * Rendered in two places: inline in the /new form's right-hand panel, and in
 * the global interrupt dialog that takes over on every other route so a run is
 * never stranded just because the user navigated away.
 */

function SelectProduct({
  products,
  product_name,
  product_url,
  onSelect,
}: {
  products: string[]
  product_name: string
  product_url: string
  onSelect: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-2 justify-center items-center h-full">
      <div className="text-center text-md">
        <p>I couldn't find <span className="font-semibold">"{product_name}"</span> anywhere on the page you shared <span className="font-semibold">({product_url})</span>. Here's what I found mentioned there:</p>
        <span className="text-sm text-balance text-muted-foreground">Select one to proceed</span>
      </div>
      <div className="grid gap-1 md:max-w-1/2">
        {
          products.map((item, index) => (
            <ButtonGroup key={`${item}-${index}`}>
              <Button size="icon" variant="ghost" onClick={() => onSelect(String(index+1))}>{index+1}</Button>
              <ButtonGroupSeparator />
              <Button variant="outline" className="cursor-pointer" onClick={() => onSelect(item)}>{item}</Button>
            </ButtonGroup>
          ))
        }
      </div>
    </div>
  )
}

function ConfirmDescription({
  product_name,
  product_desc,
  onConfirm,
}: {
  product_name: string
  product_desc: string
  onConfirm: (value: string) => void
}) {
  const [isEdit, setIsEdit] = useState(false)
  const [desc, setDesc] = useState(product_desc)

  return (
    <div className="flex flex-col gap-2 justify-center items-center h-full p-6">
      <div className={`${isEdit && 'hidden'}`}>
        <div className="flex flex-col gap-2 text-md">
          <div className="flex justify-start items-center gap-1.5">
            <div className="h-3.5 w-3.5 rounded-xs bg-[#FEA853] animate-pulse" />
            <span className="text-base font-medium">My understanding of {product_name}</span>
          </div>
          <p className="text-[15px] text-muted-foreground">{product_desc}.</p>
          <span className={`text-base`}>Is this correct?</span>
        </div>
        <div className="w-full">
          {
            ["Yes", "No"].map((item, index) => (
              <ButtonGroup key={index} className="">
                <Button size="icon" variant="ghost" className="">
                  <CornerDownRight className="" />
                </Button>
                <Button
                  variant="link"
                  onClick={() => {
                    if (item === "No") {
                      setIsEdit(!isEdit)
                    } else {
                      onConfirm("yes")
                    }
                  }}
                  className="hover:text-[#FEA853] cursor-pointer"
                >
                  {item == "Yes" ? "Yes, Proceed" : "No, I'll edit"}
                </Button>
              </ButtonGroup>
            ))
          }
        </div>
      </div>
      <div className={`${isEdit ? 'block' : 'hidden'} w-full h-full flex flex-col items-start justify-center space-y-2`}>
        <Label htmlFor="text-area-id" className="text-base text-start font-medium">
          <CornerDownRight size="16px" />
          Edit product/service description
        </Label>
        <Textarea
          id="text-area-id"
          placeholder='Type your feedback here'
          className={
            cn(
              'field-sizing-content max-h-[80%] min-h-0 resize-none py-1.75',
              'focus-visible:ring-[#FEA853] focus-visible:ring-2 focus-visible:ring-offset-0 focus-visible:border-[#FEA853]'
            )
          }
          value={desc}
          onChange={(event) => setDesc(event.target.value)}
        />
        <div className="space-x-1">
          <Button
            size="sm" className='hover:bg-[#FEA853] rounded-full px-3 cursor-pointer'
            onClick={() => setIsEdit(!isEdit)}
          >
            <X />
            Cancel
          </Button>
          <Button size="sm" className='hover:bg-[#FEA853] rounded-full px-3 cursor-pointer'
            onClick={() => {
              const value = desc.trim()
              if (value) onConfirm(value)
            }}
          >
            <ArrowUpRight />
            Proceed
          </Button>
        </div>
      </div>
    </div>
  )
}

function ClarifyUrl({
  url,
  question,
  onSubmit,
}: {
  url: string | null
  question: string | null
  onSubmit: (value: string) => void
}) {
  const [value, setValue] = useState("")

  return (
    <div className="flex flex-col gap-3 justify-center items-center h-full p-6">
      <div className="text-center text-md max-w-xl text-balance">
        <p className="text-muted-foreground">
          {question ??
            `I couldn't fetch any content from ${url ?? "the link you shared"}.`}
        </p>
        <span className="text-sm text-muted-foreground">
          Reply with a working URL, or type <span className="font-semibold">continue</span>.
        </span>
      </div>
      <form
        className="flex w-full max-w-xl items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          const trimmed = value.trim()
          if (trimmed) onSubmit(trimmed)
        }}
      >
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={url ?? "https://example.com"}
          autoFocus
        />
        <Button type="submit" disabled={!value.trim()} className="bg-[#FEA853] cursor-pointer">
          Send
        </Button>
      </form>
    </div>
  )
}

function ChooseOfferType({
  offerName,
  question,
  lean,
  onSelect,
}: {
  offerName: string | null
  question: string | null
  lean: string | null
  onSelect: (value: string) => void
}) {
  return (
    <div className="flex flex-col gap-4 justify-center items-center h-full p-6">
      <div className="text-center text-md max-w-xl text-balance">
        <p className="font-semibold">
          Is "{offerName ?? "your offer"}" a PRODUCT or a SERVICE?
        </p>
        <p className="text-sm text-muted-foreground mt-1">
          {question ??
            "Product = a thing users buy/own/use. Service = work performed."}
        </p>
        {lean && (
          <span className="text-xs text-muted-foreground">My lean: {lean}</span>
        )}
      </div>
      <div className="flex gap-3">
        {["product", "service"].map((option) => (
          <Button
            key={option}
            variant="outline"
            className="cursor-pointer capitalize"
            onClick={() => onSelect(option)}
          >
            {option}
          </Button>
        ))}
      </div>
    </div>
  )
}

/** Fallback so a future interrupt type can never strand the user. */
function UnknownInterrupt({
  question,
  onSubmit,
}: {
  question: string | null
  onSubmit: (value: string) => void
}) {
  const [value, setValue] = useState("")

  return (
    <div className="flex flex-col gap-3 justify-center items-center h-full p-6">
      <p className="text-center text-md max-w-xl text-balance text-muted-foreground">
        {question ?? "The agent needs some input to continue."}
      </p>
      <form
        className="flex w-full max-w-xl items-center gap-2"
        onSubmit={(event) => {
          event.preventDefault()
          const trimmed = value.trim()
          if (trimmed) onSubmit(trimmed)
        }}
      >
        <Input
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Type your reply…"
          autoFocus
        />
        <Button type="submit" disabled={!value.trim()} className="bg-[#FEA853] cursor-pointer">
          Send
        </Button>
      </form>
    </div>
  )
}

/**
 * Pick the right interrupt UI for a frame. `fallbackProductName`/`fallbackUrl`
 * fill in whatever the frame does not carry (the agent omits fields it has no
 * value for, e.g. url_unscrappable does not send offer_name).
 *
 * ClarifyUrl is keyed by session+url so a second unscrappable-URL interrupt
 * resets the input instead of reusing the previous value.
 */
export function DiscoveryInterruptPicker({
  interrupt,
  fallbackProductName,
  fallbackUrl,
  onAnswer,
}: {
  interrupt: DiscoveryInterruptFrame
  fallbackProductName: string
  fallbackUrl: string
  onAnswer: (value: string) => void
}) {
  switch (interrupt.interrupt_type) {
    case "offer_name_mismatch":
      return (
        <SelectProduct
          products={interrupt.product_candidates ?? []}
          product_name={interrupt.offer_name ?? fallbackProductName}
          product_url={fallbackUrl}
          onSelect={onAnswer}
        />
      )
    case "product_service_description_confirmation":
      return (
        <ConfirmDescription
          key={interrupt.draft ?? interrupt.session_id}
          product_name={interrupt.offer_name ?? fallbackProductName}
          product_desc={interrupt.draft ?? ""}
          onConfirm={onAnswer}
        />
      )
    // Retired, but deliberately still routed. The agent no longer emits this
    // interrupt — the intake form asserts `offer_type` instead — yet a run
    // checkpointed before that change can still resume onto one, and this
    // picker is what App.tsx renders for it. Deleting this case would strand
    // those threads on UnknownInterrupt. Remove it once no run can be parked
    // on it (one release after the agent change ships).
    case "offer_type_clarification":
      return (
        <ChooseOfferType
          offerName={interrupt.offer_name}
          question={interrupt.question}
          lean={interrupt.lean}
          onSelect={onAnswer}
        />
      )
    case "url_unscrappable":
      return (
        <ClarifyUrl
          key={`${interrupt.session_id}:${interrupt.url ?? ""}`}
          url={interrupt.url}
          question={interrupt.question}
          onSubmit={onAnswer}
        />
      )
    default:
      return <UnknownInterrupt question={interrupt.question} onSubmit={onAnswer} />
  }
}