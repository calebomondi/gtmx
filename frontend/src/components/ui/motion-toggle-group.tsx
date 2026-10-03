'use client'

import * as React from 'react'

import { type HTMLMotionProps, type Transition, motion, AnimatePresence } from 'motion/react'

import { cn } from '@/lib/utils'
import { ToggleGroup as BaseToggleGroup, ToggleGroupItem as BaseToggleGroupItem } from '@/components/ui/toggle-group'

type MotionToggleGroupContextProps = {
  type?: 'single' | 'multiple'
  transition?: Transition
  activeClassName?: string
  globalId: string
}

const MotionToggleGroupContext = React.createContext<MotionToggleGroupContextProps | undefined>(undefined)

const useMotionToggleGroup = (): MotionToggleGroupContextProps => {
  const context = React.useContext(MotionToggleGroupContext)

  if (!context) {
    throw new Error('useMotionToggleGroup must be used within a ToggleGroup')
  }

  return context
}

type ToggleGroupProps = React.ComponentProps<typeof BaseToggleGroup> & {
  type?: 'single' | 'multiple'
  transition?: Transition
  activeClassName?: string
}

function ToggleGroup({
  className,
  variant,
  size,
  children,
  type,
  transition = { type: 'spring', bounce: 0, stiffness: 200, damping: 25 },
  activeClassName,
  value,
  defaultValue,
  onValueChange,
  ...props
}: ToggleGroupProps) {
  const globalId = React.useId()
  const isSingle = type === 'single'

  // For single mode, keep at most one value selected and prevent deselection.
  const [singleValue, setSingleValue] = React.useState<readonly string[]>(defaultValue ?? value ?? [])

  // Keep in sync when controlled externally (single mode)
  React.useEffect(() => {
    if (isSingle && value !== undefined) {
      setSingleValue(value)
    }
  }, [isSingle, value])

  const handleSingleValueChange = React.useCallback(
    (
      newValue: string[],
      eventDetails: Parameters<NonNullable<React.ComponentProps<typeof BaseToggleGroup>['onValueChange']>>[1]
    ) => {
      // Keep only the last selected item; ignore deselect (empty array)
      if (newValue.length === 0) return

      const next = [newValue[newValue.length - 1]]

      setSingleValue(next)
      onValueChange?.(next, eventDetails)
    },
    [onValueChange]
  )

  return (
    <MotionToggleGroupContext.Provider
      value={{
        type,
        transition,
        activeClassName,
        globalId
      }}
    >
      {isSingle ? (
        <BaseToggleGroup
          className={cn('relative', className)}
          variant={variant}
          size={size}
          value={singleValue}
          onValueChange={handleSingleValueChange}
          {...props}
        >
          {children}
        </BaseToggleGroup>
      ) : (
        <BaseToggleGroup
          className={cn('relative', className)}
          variant={variant}
          size={size}
          value={value}
          defaultValue={defaultValue}
          onValueChange={onValueChange}
          {...props}
        >
          {children}
        </BaseToggleGroup>
      )}
    </MotionToggleGroupContext.Provider>
  )
}

type ToggleGroupItemProps = React.ComponentProps<typeof BaseToggleGroupItem> & {
  children?: React.ReactNode
  motionProps?: HTMLMotionProps<'div'>
  spanProps?: React.ComponentProps<'span'>
}

function ToggleGroupItem({ ref, className, children, motionProps, spanProps, ...props }: ToggleGroupItemProps) {
  const { activeClassName, transition, type, globalId } = useMotionToggleGroup()
  const itemRef = React.useRef<HTMLButtonElement | null>(null)

  React.useImperativeHandle(ref, () => itemRef.current as HTMLButtonElement)
  const [isActive, setIsActive] = React.useState(false)

  React.useEffect(() => {
    const node = itemRef.current

    if (!node) return

    const observer = new MutationObserver(() => {
      setIsActive(node.hasAttribute('data-pressed'))
    })

    observer.observe(node, {
      attributes: true,
      attributeFilter: ['data-pressed']
    })

    setIsActive(node.hasAttribute('data-pressed'))

    return () => observer.disconnect()
  }, [])

  return (
    <BaseToggleGroupItem
      ref={itemRef}
      {...props}
      className={cn('relative hover:bg-transparent data-pressed:bg-transparent', className)}
    >
      <motion.div
        data-slot='toggle-group-item-motion'
        initial={{ scale: 1 }}
        whileTap={{ scale: 0.9 }}
        {...motionProps}
        className={cn('relative flex h-full w-full items-center justify-center', motionProps?.className)}
      >
        <span {...spanProps} data-state={isActive ? 'on' : 'off'} className={cn('relative z-1', spanProps?.className)}>
          {children}
        </span>

        <AnimatePresence initial={false}>
          {isActive && type === 'single' && (
            <motion.span
              layoutId={`active-toggle-group-item-${globalId}`}
              data-slot='active-toggle-group-item'
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={transition}
              className={cn('bg-muted absolute inset-0 z-0 rounded-md', activeClassName)}
            />
          )}
        </AnimatePresence>
      </motion.div>
    </BaseToggleGroupItem>
  )
}

export { ToggleGroup, ToggleGroupItem, type ToggleGroupProps, type ToggleGroupItemProps }
