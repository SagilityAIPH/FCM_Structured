import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => {
    return (
      <textarea
        className={cn(
          "flex w-full rounded-md border border-(--color-border) bg-white px-3 py-2 text-sm shadow-sm placeholder:text-(--color-ink-muted) focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-(--color-accent) disabled:cursor-not-allowed disabled:opacity-70",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Textarea.displayName = "Textarea"

export { Textarea }
