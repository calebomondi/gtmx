"use client"

import { cn } from "@/lib/utils"
import React, { useEffect, useState } from "react"
import { codeToHtml } from "shiki"

export type CodeBlockProps = {
  children?: React.ReactNode
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlock({ children, className, ...props }: CodeBlockProps) {
  return (
    <div
      data-slot="code-block"
      className={cn("not-prose my-2 overflow-hidden rounded-lg border border-border bg-muted/30 text-sm", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export type CodeBlockCodeProps = {
  code: string
  language?: string
  theme?: string
  className?: string
} & React.HTMLProps<HTMLDivElement>

function CodeBlockCode({
  code,
  language = "tsx",
  theme = "github-dark-default",
  className,
  ...props
}: CodeBlockCodeProps) {
  const [highlightedHtml, setHighlightedHtml] = useState<string | null>(null)

  useEffect(() => {
    let isMounted = true
    async function highlight() {
      if (!code) {
        if (isMounted) setHighlightedHtml("")
        return
      }
      const html = await codeToHtml(code, { lang: language, theme })
      if (isMounted) setHighlightedHtml(html)
    }
    highlight()
    return () => {
      isMounted = false
    }
  }, [code, language, theme])

  const classNames = cn("w-full overflow-x-auto text-[13px] [&>pre]:px-4 [&>pre]:py-4", className)

  return highlightedHtml ? (
    <div
      data-slot="code-block-code"
      className={classNames}
      dangerouslySetInnerHTML={{ __html: highlightedHtml }}
      {...props}
    />
  ) : (
    <div data-slot="code-block-code" className={classNames} {...props}>
      <pre>
        <code>{code}</code>
      </pre>
    </div>
  )
}

export type CodeBlockGroupProps = React.HTMLAttributes<HTMLDivElement>

function CodeBlockGroup({ children, className, ...props }: CodeBlockGroupProps) {
  return (
    <div
      data-slot="code-block-group"
      className={cn("flex items-center justify-between border-b border-border bg-muted/40 px-4 py-2", className)}
      {...props}
    >
      {children}
    </div>
  )
}

export { CodeBlockGroup, CodeBlockCode, CodeBlock }
