import { Bot } from 'lucide-react'
import { PromptInputWithActions } from '@/components/chat-input'

export function AgentChat() {
  return (
    <div className='flex h-full flex-col'>
      <div className='border-b px-4 py-3'>
        <div className='flex items-center gap-2'>
          <span aria-hidden className='size-2 rounded-full bg-emerald-500' />
          <p className='text-sm font-medium'>GTM agent</p>
        </div>
        <p className='mt-0.5 text-xs text-muted-foreground'>
          Your conversational product/service &amp; GTM analyst.
        </p>
      </div>
      <div className='flex min-h-0 flex-1 flex-col items-center justify-center gap-4 px-6 text-center'>
        <div className='flex h-14 w-14 items-center justify-center rounded-2xl bg-amber-500/10 text-amber-500'>
          <Bot className='size-6' />
        </div>
        <div>
          <p className='text-sm font-medium text-foreground'>
            Agent chat isn't connected yet
          </p>
          <p className='mt-1 text-sm leading-relaxed text-muted-foreground'>
            Conversations with your GTM agent are coming soon. Until then, the
            agent's findings show up in the Feed, Product/Service, and
            Competitors tabs.
          </p>
        </div>
      </div>
      <div className='border-t p-3 opacity-50' aria-hidden>
        <PromptInputWithActions
          onSubmit={() => {}}
          isLoading={false}
          placeholder='Ask your agent… (coming soon)'
        />
      </div>
    </div>
  )
}

export default AgentChat
