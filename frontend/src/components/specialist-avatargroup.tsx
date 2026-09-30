import {
  AvatarGroup,
  AvatarGroupTooltip,
} from '@/components/animate-ui/components/animate/avatar-group';
import {
  Avatar,
  AvatarFallback,
  AvatarImage,
} from '@/components/ui/avatar';

export interface Specialist {
  id: string;
  fallback: string;
  /** Pre-formatted, e.g. "Product Specialist" / "GTM Specialist". */
  domain: string;
  name: string;
  role: string;
  borderClass: string;
}

export const AvatarImg: string[] = [
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-3.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-6.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-5.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-16.png'
]

// Domain, then name, then role -- a vertical stack. The fixed tooltip width (set
// by AvatarGroupTooltip) keeps every tooltip in a group the same size, so long
// roles wrap instead of making the card jump around between avatars.
function toolTip({
  domain,
  name,
  role,
  borderClass,
}: {
  domain: string;
  name: string;
  role: string;
  borderClass: Specialist['borderClass'];
}) {
  const backgroundClass = {
    'border-red-500': 'bg-red-500',
    'border-green-500': 'bg-green-500',
    'border-blue-500': 'bg-blue-500',
    'border-amber-500': 'bg-amber-500',
  }[borderClass] ?? 'bg-amber-500';

  return (
    <div className="flex flex-col items-start gap-1">
      <div className={`h-0.5 w-0 animate-tooltip-line ${backgroundClass}`} />
      <p className="font-medium text-foreground">{domain}</p>
      <p className="text-foreground">{name}</p>
      <p className="text-muted-foreground">{role}</p>
    </div>
  );
}

export const SpecialistAvatarGroup = (
  {specialists} : {specialists: Specialist[]}
) => {
  return (
    <AvatarGroup>
      {specialists.map((avatar, index) => (
        <Avatar
          key={index}
          className={`border-3 size-8 ${avatar.borderClass} cursor-pointer`}
        >
          <AvatarImage src={AvatarImg[index % AvatarImg.length]} />
          <AvatarFallback>{avatar.fallback}</AvatarFallback>
          <AvatarGroupTooltip>
            {toolTip({
              domain: avatar.domain,
              name: avatar.name,
              role: avatar.role,
              borderClass: avatar.borderClass,
            })}
          </AvatarGroupTooltip>
        </Avatar>
      ))}
    </AvatarGroup>
  );
};