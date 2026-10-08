import * as React from 'react'
import { cn } from '@/lib/utils'
export function Input({ className, ...props }: React.ComponentProps<'input'>) {
  return <input className={cn('flex h-8 w-full min-w-0 rounded-md border border-slate-200 bg-white px-2.5 text-xs text-slate-800 shadow-xs placeholder:text-slate-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:opacity-55', className)} {...props} />
}
