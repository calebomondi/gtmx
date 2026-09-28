import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'

const ButtonAvatarDemo = () => {
  return (
    <Button className='hover:bg-primary/90 rounded-full pl-2'>
      <Avatar className='size-5'>
        <AvatarImage src='https://cdn.shadcnstudio.com/ss-assets/avatar/avatar-5.png' alt='Hallie Richards' />
        <AvatarFallback className='text-foreground text-xs'>HR</AvatarFallback>
      </Avatar>
      @hallierichards
    </Button>
  )
}

export default ButtonAvatarDemo
