import { motion } from 'motion/react'
import { Bot } from 'lucide-react'

import { cn } from '@/lib/utils'
import type { WorkspaceTab } from '@/lib/workspace-tab'

import { WORKSPACE_TABS } from './workspace-tabs'

const SECTIONS = WORKSPACE_TABS.filter((t) => t.value !== 'agent')

interface NavProps {
  current: WorkspaceTab
  onSelect: (tab: WorkspaceTab) => void
  className?: string
}

/** Desktop (≥1280px): the agent bubble above a vertical list, in a column
 * beside the content rather than floating over the page. */
export function RailNav({ current, onSelect, className }: NavProps) {
  return (
    <nav aria-label="Workspace sections" className={cn('flex flex-col items-start gap-3', className)}>
      <motion.button
        type="button"
        onClick={() => onSelect('agent')}
        aria-current={current === 'agent' ? 'page' : undefined}
        aria-label="Open agent chat"
        title="Ask your agent"
        animate={{ y: [0, -4, 0] }}
        transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
        whileHover={{ scale: 1.08 }}
        whileTap={{ scale: 0.95 }}
        className={cn(
          'relative flex size-11 cursor-pointer items-center justify-center rounded-full border shadow-sm',
          current === 'agent'
            ? 'border-amber-500/70 bg-amber-500 text-white shadow-md'
            : 'border-amber-500/30 bg-amber-500/15 text-amber-500 hover:border-amber-500/60 hover:bg-amber-500/25 hover:text-amber-400',
        )}
      >
        <span aria-hidden className={cn('absolute -inset-0.5 animate-pulse rounded-full blur-md', current === 'agent' ? 'bg-amber-500/40' : 'bg-amber-500/25')} />
        <Bot className="relative size-5" />
      </motion.button>
      <ul className="flex flex-col rounded-xl bg-muted px-2 py-3 shadow-sm">
        {SECTIONS.map((tab) => (
          <li key={tab.value}>
            <button
              type="button"
              onClick={() => onSelect(tab.value)}
              aria-current={current === tab.value ? 'page' : undefined}
              className={cn(
                'relative flex h-8 w-36 cursor-pointer items-center px-3 text-sm transition-colors',
                current === tab.value ? 'text-amber-500' : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {current === tab.value && <span aria-hidden className="absolute top-0 left-0 h-full w-1 rounded-r-full bg-amber-500" />}
              {tab.name}
            </button>
          </li>
        ))}
      </ul>
    </nav>
  )
}

/** Tablet (768–1279px): one row of tabs pinned under the header. */
export function TopNav({ current, onSelect, className }: NavProps) {
  return (
    <nav aria-label="Workspace sections" className={cn('border-b border-primary/15 bg-muted/90 backdrop-blur', className)}>
      <ul className="flex h-12 items-stretch gap-1 overflow-x-auto px-2 [scrollbar-width:none]">
        {WORKSPACE_TABS.map((tab) => {
          const active = current === tab.value
          const Icon = tab.icon
          return (
            <li key={tab.value} className="flex">
              <button
                type="button"
                onClick={() => onSelect(tab.value)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'relative flex cursor-pointer items-center gap-2 px-3 text-sm whitespace-nowrap transition-colors',
                  active ? 'text-amber-500' : 'text-muted-foreground hover:text-foreground',
                  tab.value === 'agent' && 'ml-auto',
                )}
              >
                <Icon className="size-4" />
                {tab.name}
                {active && <span aria-hidden className="absolute inset-x-2 bottom-0 h-0.5 rounded-full bg-amber-500" />}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

/** Phone (<768px): a thumb-reach tab bar, clear of the home indicator. */
export function BottomNav({ current, onSelect, className }: NavProps) {
  return (
    <nav
      aria-label="Workspace sections"
      className={cn('border-t border-primary/15 bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur', className)}
    >
      <ul className="grid h-16 grid-cols-5">
        {WORKSPACE_TABS.map((tab) => {
          const active = current === tab.value
          const Icon = tab.icon
          const agent = tab.value === 'agent'
          return (
            <li key={tab.value} className="flex">
              <button
                type="button"
                onClick={() => onSelect(tab.value)}
                aria-current={active ? 'page' : undefined}
                className={cn(
                  'flex flex-1 cursor-pointer flex-col items-center justify-center gap-1 text-[11px] font-medium transition-colors',
                  active ? 'text-amber-500' : 'text-muted-foreground',
                )}
              >
                <span
                  className={cn(
                    'grid place-items-center',
                    agent ? 'size-8 rounded-full border border-amber-500/40 bg-amber-500/15 text-amber-500' : 'size-6',
                    agent && active && 'border-amber-500 bg-amber-500 text-white',
                  )}
                >
                  <Icon className={agent ? 'size-4' : 'size-5'} />
                </span>
                {tab.name}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}
