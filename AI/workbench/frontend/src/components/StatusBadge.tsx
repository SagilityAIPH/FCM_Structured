import { cn } from '@/lib/utils'
import type { Status } from '@/types'
const colors: Record<Status, string> = {
  Ready: 'bg-slate-100 text-slate-600', Queued: 'bg-slate-100 text-slate-600',
  Processing: 'bg-blue-50 text-blue-700', Completed: 'bg-emerald-50 text-emerald-700',
  'Needs Review': 'bg-amber-50 text-amber-800', Failed: 'bg-red-50 text-red-700',
}
export function StatusBadge({ status }: {status: Status}) {
  return <span className={cn('inline-flex items-center gap-1.5 rounded px-2 py-1 text-[11px] font-medium whitespace-nowrap', colors[status])}><span className={cn('size-1.5 rounded-full bg-current', status === 'Processing' && 'animate-pulse')} />{status}</span>
}
