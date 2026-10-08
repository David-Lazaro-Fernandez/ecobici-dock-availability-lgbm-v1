// Bottom sheet for phones. Closed, it shows its top down to the element that `peekTo` selects. Open, it shows all
// its content. Drag the handle, or tap it, to open or close it.

import { type CSSProperties, type ReactNode, type PointerEvent, useLayoutEffect, useRef, useState } from 'react';

// A shorter drag is a tap or an accident: the drawer stays as it is.
const DRAG_TO_TOGGLE_PX = 40;
const TAP_MAX_PX = 4;
// Before the first measure: the handle and the card title.
const FALLBACK_PEEK_PX = 120;

export type DrawerOptions = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after each render with the closed height in px, so that the map can frame the area above it. */
  onPeekChange: (px: number) => void;
  peekTo: string;
  openLabel: string;
  closeLabel: string;
};
type Props = DrawerOptions & { label: string; busy?: boolean; children: ReactNode };

export function Drawer({ open, onOpenChange, onPeekChange, peekTo, label, openLabel, closeLabel, busy, children }: Props) {
  const box = useRef<HTMLElement>(null);
  const start = useRef<number | null>(null);
  const [drag, setDrag] = useState(0);
  const [peek, setPeek] = useState(FALLBACK_PEEK_PX);

  // The transform does not change the distance from the top of the drawer to the element.
  useLayoutEffect(() => {
    const target = box.current?.querySelector(peekTo);
    if (!box.current || !target) return;
    const px = Math.ceil(target.getBoundingClientRect().bottom - box.current.getBoundingClientRect().top);
    onPeekChange(px);
    if (px !== peek) setPeek(px);
  });

  useLayoutEffect(() => {
    if (!open && box.current) box.current.scrollTop = 0;
  }, [open]);

  const down = (e: PointerEvent<HTMLButtonElement>) => {
    start.current = e.clientY;
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const move = (e: PointerEvent<HTMLButtonElement>) => {
    if (start.current != null) setDrag(e.clientY - start.current);
  };
  const up = () => {
    if (start.current == null) return;
    start.current = null;
    setDrag(0);
    if (Math.abs(drag) <= TAP_MAX_PX) onOpenChange(!open);
    else if (Math.abs(drag) >= DRAG_TO_TOGGLE_PX) onOpenChange(drag < 0);
  };

  return (
    <aside
      ref={box}
      className={`card drawer ${open ? 'is-open' : ''} ${drag ? 'is-dragging' : ''}`}
      aria-label={label}
      aria-busy={busy}
      style={{ '--peek': `${peek}px`, '--drag': `${drag}px` } as CSSProperties}
    >
      <button
        type="button"
        className="drawer__handle"
        aria-label={open ? closeLabel : openLabel}
        aria-expanded={open}
        onPointerDown={down}
        onPointerMove={move}
        onPointerUp={up}
        onPointerCancel={() => {
          start.current = null;
          setDrag(0);
        }}
        // Keyboard only: a pointer tap toggles in `up`. A keyboard click has no pointer, so its detail is 0.
        onClick={(e) => e.detail === 0 && onOpenChange(!open)}
      >
        <span className="drawer__grabber" aria-hidden="true" />
      </button>
      {children}
    </aside>
  );
}
