import { useState, type FormEvent, type ReactNode } from "react"
import { Check } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Field, FieldContent, FieldDescription, FieldError, FieldGroup, FieldLabel, FieldTitle } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Textarea } from "@/components/ui/textarea"
import type { BlockAnswerDto, ChecklistBlockDto, ChoicesBlockDto, FormBlockDto, FormFieldDto, QuestionBlockDto } from "@/lib/api"
import { cn } from "@/lib/utils"
import { isUrl, isValidEmail } from "@/lib/validation"

/** open: it can be answered now. answered: the founder answered it. closed:
 * the conversation moved on without an answer. */
type QuestionState = "open" | "answered" | "closed"

const INPUT_TYPE: Record<FormFieldDto["kind"], string> = {
  text: "text", long_text: "text", email: "email", url: "url", number: "number",
}

function Panel({ question, state, children }: { question: string; state: QuestionState; children: ReactNode }) {
  return (
    <div className={cn("flex flex-col gap-3 rounded-xl border bg-card/80 p-3 backdrop-blur-sm",
                       state === "open" && "border-theme/40 shadow-sm")}>
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium">{question}</p>
        {state === "answered" && <Badge variant="secondary" className="shrink-0"><Check /> Answered</Badge>}
        {state === "closed" && <Badge variant="outline" className="shrink-0 text-muted-foreground">Closed</Badge>}
      </div>
      {children}
    </div>
  )
}

function Choices({ block, state, answer, onAnswer }: {
  block: ChoicesBlockDto
  state: QuestionState
  answer: BlockAnswerDto | undefined
  onAnswer: (answer: BlockAnswerDto) => void
}) {
  const picked = answer?.chosen[0]
  return (
    <Panel question={block.question} state={state}>
      <div className="flex flex-wrap gap-2">
        {block.options.map((option) => (
          <Button key={option} size="sm" variant="outline" disabled={state !== "open"}
                  className={cn(option === picked && "border-theme bg-theme/15 text-foreground disabled:opacity-100")}
                  onClick={() => block.id && onAnswer({ block_id: block.id, chosen: [option], values: {} })}>
            {option === picked && <Check />} {option}
          </Button>
        ))}
      </div>
    </Panel>
  )
}

function Checklist({ block, state, answer, onAnswer }: {
  block: ChecklistBlockDto
  state: QuestionState
  answer: BlockAnswerDto | undefined
  onAnswer: (answer: BlockAnswerDto) => void
}) {
  const [ticked, setTicked] = useState<ReadonlySet<string>>(
    () => new Set(answer ? answer.chosen : block.items.filter((i) => i.checked).map((i) => i.id)))
  const shown = answer ? new Set(answer.chosen) : ticked
  const toggle = (id: string, on: boolean) => setTicked((prev) => {
    const next = new Set(prev)
    if (on) next.add(id)
    else next.delete(id)
    return next
  })
  return (
    <Panel question={block.question} state={state}>
      <FieldGroup className="gap-2">
        {block.items.map((item) => (
          <FieldLabel key={item.id} htmlFor={`${block.id}-${item.id}`}
                      className="has-data-checked:border-theme/50 has-data-checked:bg-theme/8 dark:has-data-checked:border-theme/40 dark:has-data-checked:bg-theme/10">
            <Field orientation="horizontal" data-disabled={state !== "open"}>
              <Checkbox id={`${block.id}-${item.id}`} checked={shown.has(item.id)} disabled={state !== "open"}
                        onCheckedChange={(on) => toggle(item.id, on)}
                        className="data-checked:border-theme data-checked:bg-theme data-checked:text-neutral-900 dark:data-checked:bg-theme" />
              <FieldContent>
                <FieldTitle>{item.label}</FieldTitle>
                {item.detail && <FieldDescription>{item.detail}</FieldDescription>}
              </FieldContent>
            </Field>
          </FieldLabel>
        ))}
      </FieldGroup>
      {state === "open" && (
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground tabular-nums">{ticked.size} of {block.items.length} ticked</span>
          <Button size="sm" onClick={() => onAnswer({ block_id: block.id, chosen: [...ticked], values: {} })}>
            {block.submit}
          </Button>
        </div>
      )}
    </Panel>
  )
}

function Form({ block, state, answer, onAnswer }: {
  block: FormBlockDto
  state: QuestionState
  answer: BlockAnswerDto | undefined
  onAnswer: (answer: BlockAnswerDto) => void
}) {
  const [values, setValues] = useState<Record<string, string>>(
    () => answer?.values ?? Object.fromEntries(block.fields.map((f) => [f.name, f.value ?? ""])))
  const shown = answer?.values ?? values
  // Fields whose value isn't the kind they ask for: said under each, and the answer waits.
  const [problems, setProblems] = useState<Record<string, string>>({})
  const submit = (event: FormEvent) => {
    event.preventDefault()
    const found = Object.fromEntries(block.fields.flatMap((f) => {
      const value = (values[f.name] ?? "").trim()
      if (!value) return []
      if (f.kind === "email" && !isValidEmail(value)) return [[f.name, "Enter an email address, e.g. name@acme.com"]]
      if (f.kind === "url" && !isUrl(value)) return [[f.name, "Enter a link, e.g. https://acme.com"]]
      return []
    }))
    setProblems(found)
    if (Object.keys(found).length === 0) onAnswer({ block_id: block.id, chosen: [], values })
  }
  return (
    <Panel question={block.question} state={state}>
      <form onSubmit={submit} className="flex flex-col gap-3">
        <FieldGroup className="gap-3">
          {block.fields.map((field) => {
            const id = `${block.id}-${field.name}`
            const props = {
              id, name: field.name, required: field.required, disabled: state !== "open", value: shown[field.name] ?? "",
              onChange: (e: { target: { value: string } }) => setValues((prev) => ({ ...prev, [field.name]: e.target.value })),
            }
            return (
              <Field key={field.name}>
                <FieldLabel htmlFor={id}>{field.label}{!field.required && <span className="text-muted-foreground"> (optional)</span>}</FieldLabel>
                {field.kind === "long_text" ? <Textarea rows={3} {...props} />
                  : <Input type={INPUT_TYPE[field.kind]} aria-invalid={!!problems[field.name]} {...props} />}
                {problems[field.name] && <FieldError>{problems[field.name]}</FieldError>}
              </Field>
            )
          })}
        </FieldGroup>
        {state === "open" && <Button type="submit" size="sm" className="self-end">{block.submit}</Button>}
      </form>
    </Panel>
  )
}

/** A question under a Lace reply, answered with a click: a choice, a
 * checklist or a short form. Once answered it keeps showing the answer. */
export function ChatQuestion({ block, answer, live, onAnswer }: {
  block: QuestionBlockDto
  answer: BlockAnswerDto | undefined
  /** It is under the latest reply and the Lace is free. */
  live: boolean
  onAnswer: (answer: BlockAnswerDto) => void
}) {
  const state: QuestionState = answer ? "answered" : live && block.id ? "open" : "closed"
  switch (block.type) {
    case "choices":
      return <Choices block={block} state={state} answer={answer} onAnswer={onAnswer} />
    case "checklist":
      return <Checklist block={block} state={state} answer={answer} onAnswer={onAnswer} />
    case "form":
      return <Form block={block} state={state} answer={answer} onAnswer={onAnswer} />
  }
}
