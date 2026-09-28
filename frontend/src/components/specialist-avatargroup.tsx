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
  tooltip: string;
  borderClass: string;
}

export const AvatarImg: string[] = [
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-3.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-6.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-5.png',
  'https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-16.png'
]

// display the fallback and tooltip in a vertical stack
function toolTip({
  fallback,
  tooltip,
  borderClass,
}: {
  fallback: string;
  tooltip: string;
  borderClass: Specialist['borderClass'];
}) {
  const backgroundClass = {
    'border-red-500': 'bg-red-500',
    'border-green-500': 'bg-green-500',
    'border-blue-500': 'bg-blue-500',
    'border-amber-500': 'bg-amber-500',
  }[borderClass] ?? 'bg-amber-500';

  return (
    <div className="flex flex-col items-start justify-start gap-1">
      <div className={`h-0.5 w-0 animate-tooltip-line ${backgroundClass}`} />
      <p>{fallback}</p>
      <p>{tooltip}</p>
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
          className={`border-3 size-8 ${avatar.borderClass}`}
        >
          <AvatarImage src={AvatarImg[index % AvatarImg.length]} />
          <AvatarFallback>{avatar.fallback}</AvatarFallback>
          <AvatarGroupTooltip>
            {toolTip({
              fallback: avatar.fallback,
              tooltip: avatar.tooltip,
              borderClass: avatar.borderClass,
            })}
          </AvatarGroupTooltip>
        </Avatar>
      ))}
    </AvatarGroup>
  );
};