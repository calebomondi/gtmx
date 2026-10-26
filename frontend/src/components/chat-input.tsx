"use client"

import { PromptInput, PromptInputAction, PromptInputActions, PromptInputTextarea } from "@/components/ui/prompt-input"
import { Button } from "@/components/ui/button"
import { ArrowUp, Paperclip, Square, X } from "lucide-react"
import { useRef, useState } from "react"

export interface ChatTab {
  label: string
  onClick?: () => void
  disabled?: boolean
  active?: boolean
}

export interface ChatInputProps {
  onSubmit: (message: string, files: File[]) => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
  showFolderTab?: boolean
  canvasOpen?: boolean
  folderLabel?: string
  onOpenCanvas?: () => void
  tabs?: ChatTab[]
  /** File kinds the picker offers, e.g. ".pdf,.docx". */
  accept?: string
  /** Text already in the input when it mounts. */
  defaultValue?: string
}

export function PromptInputWithActions({
  onSubmit,
  isLoading = false,
  disabled = false,
  placeholder = "Ask me anything...",
  showFolderTab = false,
  canvasOpen = false,
  folderLabel = "View Canva",
  onOpenCanvas,
  tabs = [],
  accept,
  defaultValue = "",
}: ChatInputProps) {
  const [input, setInput] = useState(defaultValue)
  const [files, setFiles] = useState<File[]>([])
  const uploadInputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    if (isLoading || disabled) return
    if (!input.trim() && files.length === 0) return

    onSubmit(input.trim(), files)
    setInput("")
    setFiles([])
  }

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files) {
      const newFiles = Array.from(event.target.files)
      setFiles((prev) => [...prev, ...newFiles])
    }
  }

  const handleRemoveFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index))
    if (uploadInputRef?.current) {
      uploadInputRef.current.value = ""
    }
  }

  const tabButtons = tabs.length
    ? tabs
    : showFolderTab
      ? [{
          label: folderLabel,
          onClick: onOpenCanvas,
          disabled: canvasOpen || !onOpenCanvas,
          active: canvasOpen,
        }]
      : []

  return (
    <div className="relative w-full max-w-(--breakpoint-md)">
      {tabButtons.length > 0 && (
        <div className="absolute left-0 top-0 z-10 flex -translate-y-[102%] items-center gap-1">
          {tabButtons.map((tab) => (
            <Button
              key={tab.label}
              size="sm"
              variant={tab.active ? "default" : "outline"}
              onClick={tab.onClick}
              disabled={tab.disabled || tab.active}
              className={[
                "mb-0.5 cursor-pointer",
                tab.active || tab.disabled
                  ? "cursor-disabled"
                  : "",
              ].join(" ")}
              style={{
                borderBottomWidth: 2,
              }}
            >
              {tab.label}
            </Button>
          ))}
        </div>
      )}

      <PromptInput
        value={input}
        onValueChange={setInput}
        isLoading={isLoading}
        onSubmit={handleSubmit}
        disabled={disabled || isLoading}
        className={[
          "w-full max-w-(--breakpoint-md) border-2 border-border shadow-sm",
          "rounded-[15px]",
        ].join(" ")}
      >
        {files.length > 0 && (
          <div className="flex flex-wrap gap-2 pb-2">
            {files.map((file, index) => (
              <div
                key={index}
                className="bg-secondary flex items-center gap-2 rounded-lg px-3 py-2 text-sm"
                onClick={(e) => e.stopPropagation()}
              >
                <Paperclip className="size-4" />
                <span className="max-w-[120px] truncate">{file.name}</span>
                <button
                  onClick={() => handleRemoveFile(index)}
                  className="hover:bg-secondary/50 rounded-full p-1"
                >
                  <X className="size-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <PromptInputTextarea
          placeholder={placeholder}
          disabled={disabled || isLoading}
        />
        <PromptInputActions className="flex items-center justify-between gap-2 pt-2">
          <PromptInputAction tooltip="Attach documents">
            <label
              htmlFor="file-upload"
              className="hover:bg-secondary-foreground/10 flex h-8 w-8 cursor-pointer items-center justify-center rounded-2xl"
            >
              <input
                type="file"
                multiple
                accept={accept}
                onChange={handleFileChange}
                className="hidden"
                id="file-upload"
                disabled={disabled || isLoading}
              />
              <Paperclip className="text-primary size-5" />
            </label>
          </PromptInputAction>
          <PromptInputAction
            tooltip={isLoading ? "Stop generation" : "Send message"}
          >
            <Button
              variant="default"
              size="icon"
              className="h-8 w-8 rounded-full"
              onClick={handleSubmit}
              disabled={disabled || isLoading}
            >
              {isLoading ? (
                <Square className="size-5 fill-current" />
              ) : (
                <ArrowUp className="size-5" />
              )}
            </Button>
          </PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    </div>
  )
}
