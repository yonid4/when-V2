'use client'

import * as React from 'react'

interface PopoverProps {
  children: React.ReactNode
  onOpenChange?: (open: boolean) => void
}

function Popover({ children, onOpenChange }: PopoverProps) {
  const [open, setOpen] = React.useState(false)
  const handleOpenChange = (next: boolean) => {
    setOpen(next)
    onOpenChange?.(next)
  }
  return (
    <div data-state={open ? 'open' : 'closed'} onClick={() => handleOpenChange(!open)}>
      {children}
    </div>
  )
}

function PopoverTrigger({ children, asChild }: { children: React.ReactNode; asChild?: boolean }) {
  return <>{children}</>
}

function PopoverContent({
  children,
  className,
  align,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { align?: string }) {
  return <div className={className} {...props}>{children}</div>
}

export { Popover, PopoverTrigger, PopoverContent }
