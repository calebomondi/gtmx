import { Bot } from 'lucide-react'
import { PromptInputWithActions } from '@/components/chat-input'
import { SpecialistAvatarGroup } from '@/components/specialist-avatargroup'
import { workspaceDisplayName } from '@/lib/api'
import { useWorkspaces } from '@/lib/workspaces-store'
import { useWorkspaceSpecialists } from '@/lib/specialists'

/**
 * Chat is scoped per workspace: `workspaceId` keys the conversation store, and
 * the header surfaces the workspace name plus that workspace's specialist team
 * so it's always clear which product/service the agent is talking about.
 * (Project-wide chat will live on the project hub as a separate agent.)
 */
export function AgentChat({ workspaceId }: { workspaceId?: string }) {
  const { workspaces } = useWorkspaces()
  const specialists = useWorkspaceSpecialists(workspaceId)

  const workspace = workspaceId
    ? workspaces.find((item) => item.id === workspaceId)
    : undefined
  const scopeName = workspace ? workspaceDisplayName(workspace) : null

  return (
    <div className='flex h-full flex-col'>
      <div className='border-b px-4 py-3'>
        <div className='flex items-center justify-between gap-2'>
          {/* <span aria-hidden className='size-2 rounded-full bg-emerald-500' /> */}
          <div>
            <p className='text-base font-medium'>{scopeName} ChatRoom</p>
            <p className='text-sm text-muted-foreground'>
              {scopeName
                ? `Converse with your specialist team.`
                : 'Converse with your specialist team.'}
            </p>
          </div>
          {/* {scopeName && (
            <span className='inline-flex max-w-40 items-center gap-1 truncate rounded-full border border-primary/10 bg-muted/60 px-2 py-0.5 text-[11px] text-muted-foreground'>
              {scopeName}
            </span>
          )} */}
          {specialists.length > 0 && (
            <div className='relative -ml-1.5'>
              <SpecialistAvatarGroup specialists={specialists} />
            </div>
          )}
        </div>
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
            Conversations with your GTM agent are coming soon
            {scopeName ? ` and will be kept per workspace (${scopeName})` : ''}.
            Until then, the agent's findings show up in the Feed,
            Product/Service, and Competitors tabs.
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