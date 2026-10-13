import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { motion } from 'motion/react'
import { Bot } from 'lucide-react'
import { Tabs, TabsContent, TabsIndicator, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { AgentChat } from '@/features/agent-chat/agent-chat'
import { FeedComponent } from '@/features/feed/feed-components'
import OutReachComponent from '@/features/outreach/outreach-components'
import ProductComponent from '@/features/product/product-components'
import CompetitionComponent from '@/features/competition/competition-components'

const TAB_DEFS = [
  { name: 'Feed', value: 'feed' },
  { name: 'Reach Out', value: 'outreach' },
  { name: 'Offer', value: 'product' },
  { name: 'Competitors', value: 'competition' },
  { name: 'Agent', value: 'agent' },
]

const TAB_VALUES = TAB_DEFS.map(t => t.value)

const TabsVerticalLined = ({ workspaceId }: { workspaceId?: string }) => {
  // The tab lives in the URL, so a link to ?tab=… (e.g. from Search) switches
  // it even when this workspace is already open.
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const tab = requested && TAB_VALUES.includes(requested) ? requested : 'feed'
  const [focus, setFocus] = useState<{ email: string | null; nonce: number }>({
    email: null,
    nonce: 0
  })

  const setTab = (next: string) => {
    setSearchParams({ tab: next }, { replace: true })
  }

  const openOutreach = (contactEmail?: string) => {
    setFocus(prev => ({ email: contactEmail ?? null, nonce: prev.nonce + 1 }))
    setTab('outreach')
  }

  const renderTabContent = (value: string) => {
    if (value === 'feed')
      return (
        <FeedComponent workspaceId={workspaceId} onOpenOutreach={openOutreach} onOpenTab={setTab} />
      )
    if (value === 'outreach')
      return (
        <OutReachComponent
          key={`${focus.email ?? 'none'}:${focus.nonce}`}
          focusEmail={focus.nonce > 0 ? focus.email : null}
          workspaceId={workspaceId}
        />
      )
    if (value === 'product') return <ProductComponent workspaceId={workspaceId} onOpenReachOut={() => setTab('outreach')} />
    if (value === 'competition') return <CompetitionComponent workspaceId={workspaceId} />
    if (value === 'agent') return <AgentChat workspaceId={workspaceId} />
  }

  return (
    <Tabs
      value={tab}
      onValueChange={setTab}
      orientation='vertical'
      className='relative w-full grid min-h-[calc(100dvh-3rem)] place-items-center bg-muted'
    >
      {/* Floating left rail — animated agent bubble above the vertical tab nav */}
      <div className='absolute top-1/2 left-4 z-10 flex -translate-y-1/2 flex-col items-start gap-3'>
        <motion.button
          type='button'
          onClick={() => setTab('agent')}
          aria-pressed={tab === 'agent'}
          aria-label='Open agent chat'
          title='Ask your agent'
          animate={{ y: [0, -4, 0] }}
          transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
          whileHover={{ scale: 1.08 }}
          whileTap={{ scale: 0.95 }}
          className={[
            'relative flex size-11 cursor-pointer items-center justify-center rounded-full border shadow-sm',
            tab === 'agent'
              ? 'border-amber-500/70 bg-amber-500 text-white shadow-md'
              : 'border-amber-500/30 bg-amber-500/15 text-amber-500 hover:border-amber-500/60 hover:bg-amber-500/25 hover:text-amber-400',
          ].join(' ')}
        >
          <span
            aria-hidden
            className={[
              'absolute -inset-0.5 rounded-full blur-md animate-pulse',
              tab === 'agent' ? 'bg-amber-500/40' : 'bg-amber-500/25',
            ].join(' ')}
          />
          <Bot className='relative size-5' />
        </motion.button>
        <TabsList className='relative flex-col rounded-xl bg-muted px-2 py-3 shadow-sm'>
          {TAB_DEFS
            .filter(t => t.value !== 'agent')
            .map(tabDef => (
              <TabsTrigger
                key={tabDef.value}
                value={tabDef.value}
                className='data-active:bg-muted data-active:text-amber-500 dark:data-active:bg-muted dark:data-active:text-amber-500 relative h-8 w-36 justify-start rounded-none border-0 px-3 data-active:shadow-none! cursor-pointer'
              >
                {tabDef.name}
              </TabsTrigger>
            ))}
          {tab !== 'agent' && (
            <TabsIndicator className='absolute top-0 left-0 h-(--active-tab-height) w-1 translate-x-(--active-tab-left) translate-y-(--active-tab-top) rounded-r-full bg-amber-500 transition-[translate,height] duration-300 ease-out' />
          )}
        </TabsList>
      </div>

      {/* Centered content column — the active tab's content renders here */}
      <div className='md:max-w-[40%] w-full border-x min-h-full border-primary/15'>
        <section className='border-b grid grid-cols-1 overflow-hidden border-primary/15'>
          {TAB_DEFS.map(tabDef => (
            <TabsContent
              key={tabDef.value}
              value={tabDef.value}
              keepMounted
              className={[
                'col-start-1 row-start-1 data-starting-style:opacity-0 data-ending-style:opacity-0 motion-safe:data-starting-style:data-[activation-direction=up]:translate-y-[-50%] motion-safe:data-starting-style:data-[activation-direction=down]:translate-y-[50%] motion-safe:data-ending-style:data-[activation-direction=up]:translate-y-[50%] motion-safe:data-ending-style:data-[activation-direction=down]:translate-y-[-50%] [transition:opacity_175ms_ease,translate_400ms_cubic-bezier(0.22,1,0.36,1)]',
                tabDef.value === 'agent' ? 'h-[calc(100dvh-3rem)] p-0' : 'px-4 pt-4',
              ].join(' ')}
            >
              {renderTabContent(tabDef.value)}
            </TabsContent>
          ))}
        </section>
      </div>
    </Tabs>
  )
}

export function ActualWorkspace({ workspaceId }: { workspaceId?: string }) {
  return <TabsVerticalLined workspaceId={workspaceId} />
}
