import * as React from "react"
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"
import { Markdown } from "./markdown"

export type MessageProps = {
  children: React.ReactNode
  className?: string
} & React.HTMLAttributes<HTMLDivElement>

const Message = ({ children, className, ...props }: MessageProps) => (
  <div data-slot="message" className={cn("flex w-full items-start", className)} {...props}>
    {children}
  </div>
)

export type MessageAvatarProps = {
  src?: string
  alt?: string
  fallback?: React.ReactNode
  delay?: number
  className?: string
}

const MessageAvatar = ({ src, alt, fallback, delay, className }: MessageAvatarProps) => {
  return (
    <Avatar
      data-slot="message-avatar"
      className={cn("size-8 shrink-0 rounded-full", className)}
    >
      {src && (
        <AvatarImage src={src} alt={alt} />
      )}
      {fallback && <AvatarFallback delay={delay}>{fallback}</AvatarFallback>}
    </Avatar>
  )
}

export type MessageContentProps = {
  children: React.ReactNode
  markdown?: boolean
  className?: string
} & React.ComponentProps<"div"> &
  React.HTMLAttributes<HTMLDivElement>

const MessageContent = ({
  children,
  markdown = false,
  className,
  ...props
}: MessageContentProps) => {
  const classNames = cn(
    "rounded-lg text-foreground prose prose-sm prose-neutral dark:prose-invert break-words whitespace-normal max-w-none prose-pre:bg-transparent prose-pre:p-0 prose-p:my-2 prose-headings:my-2 prose-ul:my-1.5 prose-ol:my-1.5 prose-li:my-0.5",
    className
  )

  return markdown ? (
    <div data-slot="message-content" className={classNames} {...props}>
      <Markdown>{children as string}</Markdown>
    </div>
  ) : (
    <div data-slot="message-content" className={classNames} {...props}>
      {children}
    </div>
  )
}

export type MessageActionsProps = {
  children: React.ReactNode
  className?: string
} & React.HTMLAttributes<HTMLDivElement>

const MessageActions = ({ children, className, ...props }: MessageActionsProps) => (
  <div data-slot="message-actions" className={cn("flex items-center ", className)} {...props}>
    {children}
  </div>
)

export type MessageActionProps = {
  className?: string
  tooltip: React.ReactNode
  children: React.ReactNode
  side?: "top" | "bottom" | "left" | "right"
} & React.ComponentProps<"button">

const MessageAction = ({
  tooltip,
  children,
  className,
  side = "top",
  ...props
}: MessageActionProps) => {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          <button
            type="button"
            data-slot="message-action"
            className={cn(
              "flex size-7 items-center justify-center rounded-md text-muted-foreground transition hover:bg-accent hover:text-foreground",
              className
            )}
            {...props}
          >
            {children}
          </button>
        </TooltipTrigger>
        <TooltipContent side={side}>{tooltip}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}

export { Message, MessageAvatar, MessageContent, MessageActions, MessageAction }
