// A forecast is never certain: show "> 99 %" and "< 1 %", never 100 % or 0 %.
const CERTAIN_ABOVE = 0.995;
const IMPOSSIBLE_BELOW = 0.005;

export function pct(p: number | null | undefined): string {
  if (p == null) return '—';
  if (p >= CERTAIN_ABOVE) return '> 99 %';
  if (p < IMPOSSIBLE_BELOW) return '< 1 %';
  return `${Math.round(p * 100)} %`;
}

export const FREE_LEGEND = ['< 50 %', '50–80 %', '80–95 %', '≥ 95 %'];

// The API name starts with the station code: "CE-017 Reforma - Río Tiber".
export const shortName = (name: string) => name.replace(/^CE-\d+\s*/, '');

/** The short names of two or more stations ("Liverpool - Génova" twice). Only those show the code. */
export function sharedNames(stations: { name: string }[]) {
  const seen = new Set<string>();
  const shared = new Set<string>();
  for (const { name } of stations) {
    const short = shortName(name);
    (seen.has(short) ? shared : seen).add(short);
  }
  return shared;
}
