import { useState } from "react"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { PendingPrompt } from "@/types"

export function PromptModal({
  prompt,
  onAnswer,
}: {
  prompt: PendingPrompt | null
  onAnswer: (value: unknown) => void
}) {
  const [text, setText] = useState("")

  if (!prompt) return null

  return (
    <Dialog open onOpenChange={() => { /* must be answered; no outside dismiss */ }}>
      <DialogContent onInteractOutside={(e) => e.preventDefault()}>
        <DialogHeader>
          <DialogTitle>{prompt.title}</DialogTitle>
          <DialogDescription>{prompt.message}</DialogDescription>
        </DialogHeader>

        {prompt.kind === "text" && (
          <Input
            autoFocus
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Type your answer"
            onKeyDown={(e) => {
              if (e.key === "Enter") onAnswer(text)
            }}
          />
        )}

        <DialogFooter>
          {prompt.kind === "yes_no" && (
            <>
              <Button variant="secondary" onClick={() => onAnswer(false)}>No</Button>
              <Button onClick={() => onAnswer(true)}>Yes</Button>
            </>
          )}
          {prompt.kind === "text" && (
            <Button onClick={() => onAnswer(text)}>Submit</Button>
          )}
          {prompt.kind === "notify" && (
            <Button onClick={() => onAnswer(null)}>OK</Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
