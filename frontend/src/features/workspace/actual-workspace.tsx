import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { AgentChat } from '@/features/agent-chat/agent-chat'
import { FeedComponent } from '@/features/feed/feed-components'
import OutReachComponent from '@/features/outreach/outreach-components'
import ProductComponent from '@/features/product/product-components'
import CompetitionComponent from '@/features/competition/competition-components'
import { BottomNav, RailNav, TopNav } from '@/features/workspace/workspace-nav'
import { WORKSPACE_TABS } from '@/features/workspace/workspace-tabs'
import { isWorkspaceTab, type WorkspaceTab } from '@/lib/workspace-tab'

const WorkspaceTabs = ({ workspaceId }: { workspaceId?: string }) => {
  // The tab lives in the URL, so a link to ?tab=… (e.g. from Search) switches
  // it even when this workspace is already open.
  const [searchParams, setSearchParams] = useSearchParams()
  const requested = searchParams.get('tab')
  const tab: WorkspaceTab = isWorkspaceTab(requested) ? requested : 'feed'
  const [focus, setFocus] = useState<{ email: string | null; nonce: number }>({
    email: null,
    nonce: 0
  })

  const setTab = (next: WorkspaceTab) => {
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
      onValueChange={(value) => setTab(value as WorkspaceTab)}
      // Vertical keeps the shared Tabs from stacking its children: here the
      // rail, column and spacer sit in one row.
      orientation='vertical'
      // Space the page chrome takes, per layout, for the tab views' heights:
      // phones add the bottom bar (and the home indicator), tablets the tab
      // row, desktops neither (the rail sits beside the content).
      className={[
        'flex min-h-[calc(100dvh-3rem)] w-full flex-row justify-center gap-0 bg-muted',
        '[--ws-chrome:calc(8rem_+_env(safe-area-inset-bottom))] md:[--ws-chrome:10rem] xl:[--ws-chrome:7rem]',
        '[--ws-agent:calc(7rem_+_env(safe-area-inset-bottom))] md:[--ws-agent:6rem] xl:[--ws-agent:3rem]',
      ].join(' ')}
    >
      <aside className='hidden w-48 shrink-0 items-center justify-end pr-5 xl:flex'>
        <RailNav current={tab} onSelect={setTab} />
      </aside>

      {/* The content widens as the screen narrows: the column has a maximum
          width, never a share of the screen, and the navigation moves. */}
      <div className='flex w-full min-w-0 max-w-3xl flex-col border-primary/15 md:border-x'>
        <TopNav current={tab} onSelect={setTab} className='hidden md:block xl:hidden' />
        <section className='grid grid-cols-1 overflow-hidden border-b border-primary/15'>
          {WORKSPACE_TABS.map(tabDef => (
            <TabsContent
              key={tabDef.value}
              value={tabDef.value}
              keepMounted
              className={[
                'col-start-1 row-start-1 data-starting-style:opacity-0 data-ending-style:opacity-0 motion-safe:data-starting-style:data-[activation-direction=up]:translate-y-[-50%] motion-safe:data-starting-style:data-[activation-direction=down]:translate-y-[50%] motion-safe:data-ending-style:data-[activation-direction=up]:translate-y-[50%] motion-safe:data-ending-style:data-[activation-direction=down]:translate-y-[-50%] [transition:opacity_175ms_ease,translate_400ms_cubic-bezier(0.22,1,0.36,1)]',
                tabDef.value === 'agent' ? 'h-[calc(100dvh-var(--ws-agent))] p-0' : 'px-4 pt-4',
              ].join(' ')}
            >
              {renderTabContent(tabDef.value)}
            </TabsContent>
          ))}
        </section>
      </div>

      {/* Balances the rail so the content sits dead centre on wide screens;
          below 1536px the room goes to the content instead. */}
      <div aria-hidden className='hidden w-48 shrink-0 2xl:block' />

      <BottomNav current={tab} onSelect={setTab} className='fixed inset-x-0 bottom-0 z-20 md:hidden' />
    </Tabs>
  )
}

export function ActualWorkspace({ workspaceId }: { workspaceId?: string }) {
  return <WorkspaceTabs workspaceId={workspaceId} />
}
