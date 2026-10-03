import { Check } from 'lucide-react'

import { cn } from '@/lib/utils'

export type SocialPlatformId = 'instagram' | 'tiktok' | 'facebook' | 'linkedin'

type SocialPlatform = {
  id: SocialPlatformId
  label: string
  src: string
  /** Real platforms prefix handles differently; the mock reflects that. */
  prefix: string
  /**
   * Optical sizing. The source glyphs have different viewBox aspect ratios and
   * different amounts of padding, so a single nominal size would make them look
   * mismatched.
   */
  glyphClassName: string
  /**
   * Only the TikTok mark needs this: its main note is white, so without a dark
   * chip behind it you see the cyan/magenta offsets and nothing else. The other
   * three carry their own background shape.
   */
  chipClassName?: string
}

const SOCIAL_PLATFORMS: SocialPlatform[] = [
  {
    id: 'instagram',
    label: 'Instagram',
    src: '/instagram.svg',
    prefix: '@',
    glyphClassName: 'size-6',
  },
  {
    id: 'tiktok',
    label: 'TikTok',
    src: '/tiktok-mark.svg',
    prefix: '@',
    glyphClassName: 'size-[22px]',
    chipClassName: 'bg-neutral-900 dark:bg-black',
  },
  {
    id: 'facebook',
    label: 'Facebook',
    src: '/facebook.svg',
    prefix: '/',
    // The mark is a circle filling 28/32 of its viewBox, so at a shared nominal
    // size it reads smaller than the square marks.
    glyphClassName: 'size-7',
  },
  {
    id: 'linkedin',
    label: 'LinkedIn',
    src: '/linkedin-mark.svg',
    prefix: 'in/',
    glyphClassName: 'size-6',
  },
]

/**
 * Mock handle. Derived from the business name so it reads like a real account
 * rather than random filler — a plausible slug is what makes the mock feel
 * wired up instead of broken.
 */
function handleFromBusinessName(name: string) {
  return name.trim().toLowerCase().replace(/[^a-z0-9]/g, '') || 'yourbrand'
}

type SocialConnectProps = {
  businessName: string
  connected: SocialPlatformId[]
  onToggle: (id: SocialPlatformId) => void
  disabled?: boolean
  className?: string
}

export function SocialConnect({
  businessName,
  connected,
  onToggle,
  disabled,
  className,
}: SocialConnectProps) {
  const handle = handleFromBusinessName(businessName)

  return (
    <div className={cn('grid grid-cols-2 gap-2 sm:grid-cols-4', className)}>
      {SOCIAL_PLATFORMS.map((platform) => {
        const isOn = connected.includes(platform.id)

        return (
          <button
            key={platform.id}
            type="button"
            aria-pressed={isOn}
            disabled={disabled}
            onClick={() => onToggle(platform.id)}
            className={cn(
              'group relative flex cursor-pointer flex-col items-center gap-1.5 rounded-lg border p-3 transition-colors',
              'focus-visible:ring-ring/50 focus-visible:ring-3 focus-visible:outline-none',
              'disabled:cursor-not-allowed disabled:opacity-50',
              isOn
                ? 'border-foreground/15 bg-card'
                : 'border-transparent bg-muted/50 hover:bg-muted',
            )}
          >
            <span
              className={cn(
                'grid size-9 place-items-center rounded-md transition-opacity',
                platform.chipClassName,
                !isOn && 'opacity-55 group-hover:opacity-100',
              )}
            >
              <img
                src={platform.src}
                alt=""
                aria-hidden="true"
                className={cn('object-contain', platform.glyphClassName)}
              />
            </span>

            <span className="text-xs font-medium">{platform.label}</span>

            <span className="max-w-full truncate text-[11px] text-muted-foreground">
              {platform.prefix}
              {handle}
            </span>

            {isOn && (
              <span
                aria-hidden="true"
                className="bg-foreground text-background absolute top-1.5 right-1.5 grid size-4 place-items-center rounded-full"
              >
                <Check className="size-2.5" strokeWidth={3} />
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
