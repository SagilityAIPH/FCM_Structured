import { useState } from 'react'
import type { PendingPrompt } from '@/types'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '@/components/ui/dialog'

export function LivePrompt({prompt, answer}: {prompt: PendingPrompt; answer: (id: string, value: boolean) => Promise<void>}) {
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const send = async (value: boolean) => {
    setSending(true); setError('')
    try { await answer(prompt.id, value) }
    catch (err) { setError((err as Error).message) }
    finally { setSending(false) }
  }
  return <Dialog open><DialogContent className="live-prompt" onEscapeKeyDown={e => e.preventDefault()} onPointerDownOutside={e => e.preventDefault()}>
    <DialogHeader><DialogTitle>{prompt.title}</DialogTitle><DialogDescription>{prompt.message}</DialogDescription></DialogHeader>
    {error && <p role="alert" className="inline-error">{error}</p>}
    <DialogFooter>{prompt.kind === 'confirm' ? <>
      <Button variant="outline" disabled={sending} onClick={() => void send(false)}>No</Button>
      <Button disabled={sending} onClick={() => void send(true)}>Yes</Button>
    </> : <Button disabled={sending} onClick={() => void send(true)}>Acknowledge</Button>}</DialogFooter>
  </DialogContent></Dialog>
}
