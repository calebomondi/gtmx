import { useEffect, useMemo, useRef, useState } from "react"
import { useNavigate } from "react-router-dom"

import { cn } from "cn"

import { Button } from "@/components/ui/button"
import {
  ButtonGroup,
  ButtonGroupSeparator,
} from "@/components/ui/button-group"
import { Card, CardContent } from "@/components/ui/card"
import {
  Field,
  FieldDescription,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { CornerDownRight, X, ArrowUpRight } from "lucide-react"
import { useDiscovery } from "@/hooks/use-discovery"

type NewWorkspaceFormProps = React.ComponentProps<"div"> & {
  isDiscovering: boolean
  setIsDiscovering: React.Dispatch<React.SetStateAction<boolean>>
}

function SelectProduct(
  {
    products,
    product_name, 
    product_url, 
    onSelect
  } : {
    products: string[];
    product_name: string; 
    product_url: string; 
    onSelect: (value: string) => void;
  }
) {
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

function ConfirmDescription(
  { 
    product_name, 
    product_desc, 
    onConfirm 
  } : {
    product_name: string;
    product_desc: string;
    onConfirm: (value: string) => void;
  }
) {
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
                  <CornerDownRight className=""/>
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

function ClarifyUrl(
  {
    url,
    question,
    onSubmit,
  }: {
    url: string | null
    question: string | null
    onSubmit: (value: string) => void
  },
) {
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

function ChooseOfferType(
  {
    offerName,
    question,
    lean,
    onSelect,
  }: {
    offerName: string | null
    question: string | null
    lean: string | null
    onSelect: (value: string) => void
  },
) {
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

export function NewWorkspaceForm({
  className,
  isDiscovering,
  setIsDiscovering,
  ...props
}: NewWorkspaceFormProps) {
  const [productName, setProductName] = useState("")
  const [websiteUrl, setWebsiteUrl] = useState("")
  const [targetGeo, setTargetGeo] = useState("")
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
    if (stage === "connecting" || stage === "awaiting_input" || stage === "running") {
      setIsDiscovering(true)
    } else if (stage === "idle" || stage === "completed" || stage === "error") {
      setIsDiscovering(false)
    }
  }, [stage, setIsDiscovering])

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

    if (!isFormReady || isDiscovering) {
      return
    }

    const target_geo = targetGeo
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean)

    setIsDiscovering(true)
    setSelectedProduct(null)
    setConfirmed(false)
    void start({
      product_name: productName,
      product_url: websiteUrl,
      target_geo: target_geo.length > 0 ? target_geo : undefined,
    })
  }

  return (
    <div className={cn("flex flex-col", className)} {...props}>
      <Card className="overflow-hidden p-0 shadow-lg">
        <CardContent className={cn("grid p-0", isDiscovering && "md:grid-cols-2")}>
          <form className="p-6 md:p-8" onSubmit={handleSubmit}>
            <FieldGroup>
              <div className="flex flex-col items-center gap-2 text-center">
                <h1 className="text-xl font-bold">Create a product/service workspace</h1>
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
                  disabled={isDiscovering}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="website-url">
                  Website URL <span className="text-[var(--destructive)]">*</span>
                </FieldLabel>
                <FieldDescription>The product/service page</FieldDescription>
                <Input
                  id="website-url"
                  value={websiteUrl}
                  onChange={(event) => setWebsiteUrl(event.target.value)}
                  placeholder="https://example.com"
                  required
                  disabled={isDiscovering}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="target-geo">
                  Target Geo <span className="text-xs">(optional)</span>
                </FieldLabel>
                <FieldDescription>Leave empty for me to decide</FieldDescription>
                <Input
                  id="target-geo"
                  value={targetGeo}
                  onChange={(event) => setTargetGeo(event.target.value)}
                  placeholder="KE, US, EU"
                  disabled={isDiscovering}
                />
              </Field>

              <Field>
                <Button type="submit" disabled={!isFormReady || isDiscovering} className={`bg-[#FEA853] ${isDiscovering ? 'cursor-not-allowed' : 'cursor-pointer'}`}>
                  {isDiscovering ? "Started workspace creation..." : "Create Workspace"}
                </Button>
              </Field>
            </FieldGroup>
          </form>
          <div
            className={cn(
              "relative bg-muted flex-col gap-3 overflow-hidden transition-all duration-300 ease-out",
              isDiscovering
                ? "flex opacity-100 scale-100 md:justify-center md:items-center"
                : "hidden opacity-0 scale-95",
            )}
          >
            {select && (
              <SelectProduct
                products={currentInterrupt?.product_candidates ?? []}
                product_name={currentInterrupt?.offer_name ?? productName}
                product_url={websiteUrl}
                onSelect={(value) => {
                  const candidates = currentInterrupt?.product_candidates ?? []
                  const chosen = /^\d+$/.test(value)
                    ? candidates[Number(value) - 1] ?? null
                    : value
                  if (chosen) setSelectedProduct(chosen)
                  answer(value)
                }}
              />
            )}
            {confirm && currentInterrupt && (
              <ConfirmDescription
                key={currentInterrupt.draft ?? currentInterrupt.session_id}
                product_name={currentInterrupt?.offer_name ?? selectedProduct ?? productName}
                product_desc={currentInterrupt.draft ?? ""}
                onConfirm={(value) => {
                  if (value) {
                    if (/^yes$/i.test(value.trim())) setConfirmed(true)
                    answer(value)
                  }
                }}
              />
            )}
            {clarifyUrl && currentInterrupt && (
              <ClarifyUrl
                key={currentInterrupt.session_id}
                url={currentInterrupt.url}
                question={currentInterrupt.question}
                onSubmit={answer}
              />
            )}
            {chooseType && currentInterrupt && (
              <ChooseOfferType
                key={currentInterrupt.session_id}
                offerName={currentInterrupt.offer_name}
                question={currentInterrupt.question}
                lean={currentInterrupt.lean}
                onSelect={answer}
              />
            )}
            {isDiscovering && (select || confirm || clarifyUrl || chooseType) && (
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