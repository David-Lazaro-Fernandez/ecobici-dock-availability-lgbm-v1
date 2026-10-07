// Stations that cannot be recommended always go last. The expected time breaks ties.

import type { Candidate } from './api';

export type SortKey = 'time' | 'walk' | 'free';

const last = (v: number | null | undefined) => (v == null ? Infinity : v);

const BY: Record<SortKey, (a: Candidate, b: Candidate) => number> = {
  // The planner ranking: ride + walk + P(full) × failure cost.
  time: (a, b) => last(a.expected_min) - last(b.expected_min),
  walk: (a, b) => a.walk_m - b.walk_m,
  free: (a, b) => (b.p_free ?? -1) - (a.p_free ?? -1),
};

export function sortCandidates(candidates: Candidate[], key: SortKey): Candidate[] {
  const ok = candidates.filter((c) => c.recommendable);
  const rest = candidates.filter((c) => !c.recommendable);
  const by = BY[key];
  ok.sort((a, b) => by(a, b) || last(a.expected_min) - last(b.expected_min) || a.walk_m - b.walk_m);
  rest.sort((a, b) => a.walk_m - b.walk_m);
  return [...ok, ...rest];
}
