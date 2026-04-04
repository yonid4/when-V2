'use client'

import * as React from 'react'

interface PopoverContextValue {
  open: boolean
  setOpen: (open: boolean) => void
}

const PopoverContext = React.createContext<PopoverContextValue>({ open: false, setOpen: () => {} })

function Popover({ children, onOpenChange }: { children: React.ReactNode; onOpenChange?: (open: boolean) => void }) {
  const [open, setOpen] = React.useState(false)
  const ref = React.useRef<HTMLDivElement>(null)

  const handleSetOpen = (next: boolean) => {
    setOpen(next)
    onOpenChange?.(next)
  }

  // Close on click outside
  React.useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        handleSetOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  return (
    <PopoverContext.Provider value={{ open, setOpen: handleSetOpen }}>
      <div ref={ref} style={{ position: 'relative', display: 'inline-block' }}>
        {children}
      </div>
    </PopoverContext.Provider>
  )
}

function PopoverTrigger({ children }: { children: React.ReactNode; asChild?: boolean }) {
  const { open, setOpen } = React.useContext(PopoverContext)
  const child = React.Children.only(children) as React.ReactElement<React.HTMLAttributes<HTMLElement>>
  return React.cloneElement(child, {
    onClick: (e: React.MouseEvent<HTMLElement>) => {
      e.stopPropagation()
      child.props.onClick?.(e)
      setOpen(!open)
    },
  })
}

function PopoverContent({
  children,
  className,
  align,
  ...props
}: React.HTMLAttributes<HTMLDivElement> & { align?: string }) {
  const { open } = React.useContext(PopoverContext)
  if (!open) return null

  const alignStyle: React.CSSProperties =
    align === 'end'
      ? { position: 'absolute', top: '100%', right: 0, marginTop: '8px', zIndex: 50 }
      : { position: 'absolute', top: '100%', left: 0, marginTop: '8px', zIndex: 50 }

  return (
    <div style={alignStyle} className={className} {...props}>
      {children}
    </div>
  )
}

export { Popover, PopoverTrigger, PopoverContent }
