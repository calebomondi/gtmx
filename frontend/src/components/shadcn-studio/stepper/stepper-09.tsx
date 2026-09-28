import { useState } from 'react'
import {
  Stepper,
  StepperItem,
  StepperTrigger,
  StepperIndicator,
  StepperSeparator,
  StepperNav,
  StepperTitle,
  StepperPanel,
  StepperDescription,
  StepperContent
} from '@/components/ui/stepper'
import { Button } from '@/components/ui/button'
import { BookOpenIcon, CodeIcon, AwardIcon, ArrowLeftIcon, ArrowRightIcon } from "lucide-react"

const steps = [
  {
    id: 'details',
    title: 'Details',
    description: 'Enter the required details for this step',
    icon: (
      <BookOpenIcon
      />
    )
  },
  {
    id: 'review',
    title: 'Review',
    description: 'Confirm your information and choices',
    icon: (
      <CodeIcon
      />
    )
  },
  {
    id: 'done',
    title: 'Done',
    description: 'All set. review completed',
    icon: (
      <AwardIcon
      />
    )
  }
]

const StepperVerticalDemo = () => {
  const [current, setCurrent] = useState(steps[0].id)

  const currentIndex = steps.findIndex(s => s.id === current)
  const goNext = () => setCurrent(steps[Math.min(currentIndex + 1, steps.length - 1)].id)
  const goBack = () => setCurrent(steps[Math.max(currentIndex - 1, 0)].id)

  return (
    <div className='flex items-center justify-center'>
      <Stepper
        steps={steps}
        value={current}
        onValueChange={setCurrent}
        className='flex items-center justify-center gap-10 max-lg:flex-col max-lg:items-start'
        orientation='vertical'
      >
        <StepperNav className='w-60'>
          {steps.map((step, index) => (
            <StepperItem key={step.id} stepId={step.id} className='relative items-start'>
              <StepperTrigger className='items-start gap-2.5 pb-15 last:pb-0'>
                <StepperIndicator>{index + 1}</StepperIndicator>
                <div className='text-left'>
                  <StepperTitle>{step.title}</StepperTitle>
                  <StepperDescription>{step.description}</StepperDescription>
                </div>
              </StepperTrigger>
              {index < steps.length - 1 && (
                <StepperSeparator className='absolute inset-y-0 top-[calc(50%-22px)] left-2 group-data-[orientation=vertical]/stepper-nav:h-15' />
              )}
            </StepperItem>
          ))}
        </StepperNav>
        <StepperPanel className='w-xs text-center text-sm sm:w-116'>
          {steps.map(step => (
            <StepperContent key={step.id} value={step.id}>
              <div className='bg-muted border-primary/15 flex flex-col items-center gap-4 rounded-lg border-2 border-dashed p-4 md:p-8'>
                <div className='space-y-2'>
                  <h3 className='text-muted-foreground text-lg font-medium'>{step.title}</h3>
                  <p className='text-muted-foreground text-sm'>{step.description}</p>
                </div>

                <div className='w-full'>
                  <div className='text-muted-foreground flex h-36 items-center justify-center'>
                    <span className='text-base'>{step.title} content</span>
                  </div>

                  <div className='mt-6 flex items-center justify-between'>
                    <Button
                      onClick={goBack}
                      disabled={currentIndex === 0}
                      variant={currentIndex === 0 ? 'secondary' : 'default'}
                    >
                      <ArrowLeftIcon className='size-4' />{' '}
                      Back
                    </Button>

                    <Button
                      onClick={goNext}
                      disabled={currentIndex === steps.length - 1}
                      variant={currentIndex === steps.length - 1 ? 'secondary' : 'default'}
                    >
                      Next{' '}
                      <ArrowRightIcon className='size-4' />
                    </Button>
                  </div>
                </div>
              </div>
            </StepperContent>
          ))}
        </StepperPanel>
      </Stepper>
    </div>
  )
}

export default StepperVerticalDemo
