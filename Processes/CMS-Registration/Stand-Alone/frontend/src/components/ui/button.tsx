import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva('inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap rounded-md text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-45 [&_svg]:size-3.5', {
  variants: {
    variant: { default: 'bg-blue-600 text-white hover:bg-blue-700 border border-blue-600 shadow-xs', outline: 'border border-slate-200 bg-white text-slate-700 hover:bg-slate-50 shadow-xs', ghost: 'text-slate-500 hover:bg-slate-100 hover:text-slate-900' },
    size: { default: 'h-8 px-3', sm: 'h-7 px-2', icon: 'h-7 w-7' },
  }, defaultVariants: { variant: 'default', size: 'default' },
})
export function Button({ className, variant, size, asChild = false, ...props }: React.ComponentProps<'button'> & VariantProps<typeof buttonVariants> & { asChild?: boolean }) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />
}
