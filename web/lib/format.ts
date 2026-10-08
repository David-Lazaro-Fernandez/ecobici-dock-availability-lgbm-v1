// A forecast is never certain: show "> 99 %" and "< 1 %", never 100 % or 0 %.
const CERTAIN_ABOVE = 0.995;
const IMPOSSIBLE_BELOW = 0.005;

export function pct(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p >= CERTAIN_ABOVE) return '> 99 %';
  if (p < IMPOSSIBLE_BELOW) return '< 1 %';
  return `${Math.round(p * 100)} %`;
}
