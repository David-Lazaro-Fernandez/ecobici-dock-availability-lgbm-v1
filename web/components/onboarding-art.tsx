// Flat illustrations for the help steps, drawn for this app. They sit on the dark green of the modal.

const PAPER = '#ffffff';
const MAP = '#f4f7f2';
const STREET = '#dde6da';
const PARK = '#cfe9d5';
const LIGHT_GREEN = '#63bf75';
const GREEN = '#168f3d';
const DARK_GREEN = '#0e6b2e';
const DEEP_GREEN = '#08431c';
const START = '#eb6834';
const ROUTE = '#3987e5';
const INK = '#0b0b0b';

const frame = { viewBox: '0 0 280 180', role: 'img' as const, className: 'help__art' };

function Glow() {
  return <circle cx="140" cy="95" r="82" fill={PAPER} opacity="0.07" />;
}

function MapCard() {
  return (
    <>
      <rect x="50" y="34" width="180" height="122" rx="16" fill={MAP} />
      <rect x="150" y="104" width="56" height="38" rx="7" fill={PARK} />
      <path d="M50 92h180M118 34v122M50 140 230 58" stroke={STREET} strokeWidth="8" />
      <path d="M50 120h68M176 34v58" stroke={STREET} strokeWidth="4" />
    </>
  );
}

function StartDot({ x, y }: { x: number; y: number }) {
  return (
    <>
      <circle cx={x} cy={y} r="20" fill={START} opacity="0.22" />
      <circle cx={x} cy={y} r="8.5" fill={START} stroke={PAPER} strokeWidth="3" />
    </>
  );
}

export function StartArt({ label }: { label: string }) {
  return (
    <svg {...frame} aria-label={label}>
      <Glow />
      <MapCard />
      <StartDot x={118} y={92} />
      <rect x="72" y="16" width="136" height="30" rx="15" fill={PAPER} />
      <circle cx="91" cy="31" r="5.5" fill="none" stroke={GREEN} strokeWidth="2.5" />
      <path d="m95 35 4 4" stroke={GREEN} strokeWidth="2.5" strokeLinecap="round" />
      <rect x="106" y="27" width="80" height="8" rx="4" fill={STREET} />
    </svg>
  );
}

export function GoalArt({ label }: { label: string }) {
  return (
    <svg {...frame} aria-label={label}>
      <Glow />
      <MapCard />
      <circle cx="184" cy="80" r="32" fill={INK} opacity="0.06" stroke={INK} strokeOpacity="0.35" strokeDasharray="4 4" />
      <path d="M82 128c22-4 30-30 56-36s38 4 46-12" fill="none" stroke={ROUTE} strokeWidth="4" strokeLinecap="round" />
      <StartDot x={82} y={128} />
      <path d="M184 82s-15-13-15-25a15 15 0 0 1 30 0c0 12-15 25-15 25Z" fill={INK} stroke={PAPER} strokeWidth="2.5" />
      <circle cx="184" cy="57" r="5.5" fill={PAPER} />
    </svg>
  );
}

function Badge({ x, y, n, fill, text }: { x: number; y: number; n: number; fill: string; text: string }) {
  return (
    <>
      <circle cx={x} cy={y} r="14" fill={fill} stroke={PAPER} strokeWidth="2.5" />
      <text x={x} y={y + 5} textAnchor="middle" fontSize="15" fontWeight="800" fill={text} fontFamily="system-ui, sans-serif">
        {n}
      </text>
    </>
  );
}

export function RecommendArt({ label }: { label: string }) {
  return (
    <svg {...frame} aria-label={label}>
      <Glow />
      <ellipse cx="140" cy="160" rx="118" ry="9" fill={PAPER} opacity="0.12" />
      <rect x="186" y="74" width="16" height="86" rx="4" fill={MAP} />
      <rect x="176" y="54" width="36" height="28" rx="6" fill={PAPER} />
      <rect x="183" y="61" width="22" height="6" rx="3" fill={LIGHT_GREEN} />
      <rect x="183" y="71" width="14" height="4" rx="2" fill={STREET} />
      <rect x="166" y="132" width="56" height="10" rx="5" fill={PARK} />
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="76" cy="134" r="24" stroke={PAPER} strokeWidth="5" />
        <circle cx="144" cy="134" r="24" stroke={PAPER} strokeWidth="5" />
        <path d="M76 134 100 100h32l12 34M100 100l16 34 16-34M94 92h14M128 100l6-14h10" stroke={LIGHT_GREEN} strokeWidth="5.5" />
      </g>
      <circle cx="76" cy="134" r="4" fill={PAPER} />
      <circle cx="144" cy="134" r="4" fill={PAPER} />
      <circle cx="116" cy="134" r="5" fill={PAPER} />
      <Badge x={212} y={44} n={1} fill={LIGHT_GREEN} text={DEEP_GREEN} />
      <Badge x={58} y={74} n={2} fill={PAPER} text={DEEP_GREEN} />
    </svg>
  );
}

export function ChanceArt({ label }: { label: string }) {
  const ramp = [LIGHT_GREEN, GREEN, DARK_GREEN, DEEP_GREEN];
  return (
    <svg {...frame} aria-label={label}>
      <Glow />
      <rect x="66" y="34" width="148" height="76" rx="16" fill={PAPER} />
      <path d="M126 110h28l-14 14Z" fill={PAPER} />
      <text x="140" y="86" textAnchor="middle" fontSize="36" fontWeight="800" fill={DEEP_GREEN} fontFamily="system-ui, sans-serif">
        95 %
      </text>
      <circle cx="212" cy="38" r="18" fill={LIGHT_GREEN} stroke={PAPER} strokeWidth="3" />
      <path d="M212 28v10l7 5" fill="none" stroke={DEEP_GREEN} strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
      {ramp.map((color, i) => (
        <rect key={color} x={78 + i * 32} y="140" width="28" height="12" rx="6" fill={color} stroke={PAPER} strokeWidth="1.5" />
      ))}
    </svg>
  );
}
