// Small flags for the language switch, in a 3:2 box. The Mexican coat of arms is a plain disc at this size.

import { useId } from 'react';

const box = { className: 'flag', 'aria-hidden': true } as const;

export function MxFlag() {
  return (
    <svg {...box} viewBox="0 0 30 20">
      <rect width="10" height="20" fill="#006847" />
      <rect x="10" width="10" height="20" fill="#ffffff" />
      <rect x="20" width="10" height="20" fill="#ce1126" />
      <circle cx="15" cy="10" r="3" fill="#8c5a2b" />
      <path d="M12 11.5a3.4 3.4 0 0 0 6 0" fill="none" stroke="#006847" strokeWidth="1" />
    </svg>
  );
}

export function GbFlag() {
  // Two flags on one page would share a clip path id.
  const diagonals = useId();
  return (
    <svg {...box} viewBox="0 0 60 30" preserveAspectRatio="xMidYMid slice">
      <clipPath id={diagonals}>
        <path d="M30 15h30v15zv15H0zH0V0zV0h30z" />
      </clipPath>
      <rect width="60" height="30" fill="#012169" />
      <path d="M0 0l60 30m0-30L0 30" stroke="#ffffff" strokeWidth="6" />
      <path d="M0 0l60 30m0-30L0 30" clipPath={`url(#${diagonals})`} stroke="#c8102e" strokeWidth="4" />
      <path d="M30 0v30M0 15h60" stroke="#ffffff" strokeWidth="10" />
      <path d="M30 0v30M0 15h60" stroke="#c8102e" strokeWidth="6" />
    </svg>
  );
}
