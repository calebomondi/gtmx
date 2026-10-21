import type { BlockAnswerDto, LaceMessageDto, QuestionBlockDto, UiBlockDto } from "@/lib/api"

export function isQuestion(block: UiBlockDto): block is QuestionBlockDto {
  return block.type !== "card"
}

/** Every answered question in the conversation, by the question's id. */
export function answersByBlock(messages: LaceMessageDto[]): ReadonlyMap<string, BlockAnswerDto> {
  return new Map(messages.flatMap((m) => (m.answer ? [[m.answer.block_id, m.answer] as const] : [])))
}

/** The founder's answer as their message, until the server's own wording
 * arrives with the next load. */
export function answerLine(block: QuestionBlockDto, answer: BlockAnswerDto): string {
  switch (block.type) {
    case "choices":
      return answer.chosen[0] ?? ""
    case "checklist": {
      const ticked = block.items.filter((item) => answer.chosen.includes(item.id)).map((item) => item.label)
      return ticked.length ? `${block.submit}: ${ticked.join(", ")}` : "None of these"
    }
    case "form":
      return block.fields.filter((f) => answer.values[f.name]?.trim())
        .map((f) => `${f.label}: ${answer.values[f.name].trim()}`).join(" · ")
  }
}
