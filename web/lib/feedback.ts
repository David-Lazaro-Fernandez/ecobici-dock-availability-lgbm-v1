// Anonymous feedback to POST /v1/feedback (src/ecobici/feedback.py). Only station ids, times, the probabilities shown
// and the answer leave the browser: no addresses, no coordinates.

import { API_URL } from '@/lib/api';

export type Reason = 'far' | 'wrong_time' | 'wrong_data' | 'other';
export type DockAnswer = 'yes' | 'no' | 'no_trip';

/** The plan the person saw. These fields go to the API. */
export type Shown = {
  plan_id: string;
  captured_at: string;
  pickup_id: string;
  dropoff_id: string;
  rank: number | null;
  arrive_at: string;
  p_free: number | null;
  p_empty_at_arrival: number | null;
};

/** The last plan, kept in this browser to ask about the trip later. The names stay in the browser. */
export type Trip = {
  shown: Shown;
  pickupName: string;
  dropoffName: string;
  /** When to ask, in ms since the epoch. */
  askAt: number;
  answered: boolean;
};

export type Answer =
  | { kind: 'rating'; useful: boolean; reason?: Reason; comment?: string }
  | { kind: 'trip'; found_dock: DockAnswer; found_bike?: 'yes' | 'no' };

export async function sendFeedback(shown: Shown, answer: Answer) {
  const res = await fetch(`${API_URL}/v1/feedback`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...shown, ...answer }),
  });
  if (!res.ok) throw new Error(String(res.status));
}
