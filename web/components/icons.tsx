// Line icons in currentColor.

const base = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: 1.7, 'aria-hidden': true } as const;

export function Sliders() {
  return (
    <svg {...base}>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" strokeLinecap="round" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </svg>
  );
}

export function Locate() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="6.5" />
      <circle cx="12" cy="12" r="2" />
      <path d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3" strokeLinecap="round" />
    </svg>
  );
}

export function Send() {
  return (
    <svg {...base} strokeWidth={2}>
      <path d="M12 19V5M5.5 11.5 12 5l6.5 6.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Pin() {
  return (
    <svg {...base}>
      <path d="M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 0 1 13 0c0 5.4-6.5 11-6.5 11Z" strokeLinejoin="round" />
      <circle cx="12" cy="10" r="2.3" />
    </svg>
  );
}

export function Dock() {
  return (
    <svg {...base}>
      <path d="M2.5 20.5V6L6 3.5v17Z" strokeLinejoin="round" />
      {/* The post hides the left part of the front wheel, as in the Ecobici logo. The bike is in the dock. */}
      <path d="M7.6 12.3A3.8 3.8 0 1 1 7.6 19.7" />
      <circle cx="19.6" cy="16" r="3.5" />
      <path d="M8.5 16 11 9M10 8.5h3M10.7 11.5 15 16h4.6M15 16l1.8-6.5M15.6 9.5h2.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Walk() {
  return (
    <svg {...base}>
      <circle cx="13" cy="4.5" r="1.8" />
      <path d="m10 21 2-6 3 3v3M8 12l2-4 4 1 2 3M12 15l-1.5-3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Close() {
  return (
    <svg {...base} strokeWidth={2}>
      <path d="M6 6l12 12M18 6 6 18" strokeLinecap="round" />
    </svg>
  );
}

export function Clock() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function ThumbUp() {
  return (
    <svg {...base}>
      <path d="M7 10.5v9H4.5v-9H7Zm0 0 3.5-7c1.4 0 2.5 1.1 2.5 2.5V9h5a2 2 0 0 1 2 2.3l-1.2 6.5a2 2 0 0 1-2 1.7H7" strokeLinejoin="round" />
    </svg>
  );
}

export function ThumbDown() {
  return (
    <svg {...base} style={{ transform: 'rotate(180deg)' }}>
      <path d="M7 10.5v9H4.5v-9H7Zm0 0 3.5-7c1.4 0 2.5 1.1 2.5 2.5V9h5a2 2 0 0 1 2 2.3l-1.2 6.5a2 2 0 0 1-2 1.7H7" strokeLinejoin="round" />
    </svg>
  );
}

export function Help() {
  return (
    <svg {...base}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M9.6 9.5a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.4" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="12" cy="16.8" r="0.6" fill="currentColor" />
    </svg>
  );
}

export function Bike() {
  return (
    <svg {...base}>
      <circle cx="6.5" cy="14" r="3.8" />
      <circle cx="17.6" cy="14" r="3.5" />
      <path d="M6.5 14 9 7M8 6.5h3M8.7 9.5 13 14h4.6M13 14l1.8-6.5M13.6 7.5h2.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function More() {
  return (
    <svg {...base} fill="currentColor" stroke="none">
      <circle cx="6" cy="12" r="1.6" />
      <circle cx="12" cy="12" r="1.6" />
      <circle cx="18" cy="12" r="1.6" />
    </svg>
  );
}
