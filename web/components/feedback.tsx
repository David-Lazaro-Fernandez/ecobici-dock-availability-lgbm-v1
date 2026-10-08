'use client';

// Two anonymous questions: "was this useful?" under the plan, and "did you find a dock?" after the arrival.

import { useEffect, useRef, useState } from 'react';
import { type Answer, type DockAnswer, type Reason, type Shown, type Trip, sendFeedback } from '@/lib/feedback';
import { dueTrip, markAnswered } from '@/lib/trip';
import { Close, ThumbDown, ThumbUp } from '@/components/icons';

const CHECK_MS = 60_000;
// In `next dev`, ask at once about the last plan, so the question can be checked without a ride.
const DEV = process.env.NODE_ENV === 'development';
const DEV_CHECK_MS = 2_000;
const THANKS_MS = 4_000;
const PRIVACY = 'Anónimo. Guardamos solo las estaciones y tu respuesta para mejorar el modelo.';
const REASONS: { key: Reason; label: string }[] = [
  { key: 'far', label: 'Me deja lejos' },
  { key: 'wrong_time', label: 'El tiempo no cuadra' },
  { key: 'wrong_data', label: 'Datos incorrectos' },
  { key: 'other', label: 'Otra razón' },
];

type Status = 'ask' | 'sending' | 'sent' | 'failed';

function useSend(shown: Shown | null) {
  const [status, setStatus] = useState<Status>('ask');
  const send = (answer: Answer, after?: () => void) => {
    if (!shown) return;
    setStatus('sending');
    sendFeedback(shown, answer)
      .then(() => {
        setStatus('sent');
        after?.();
      })
      .catch(() => setStatus('failed'));
  };
  return { status, send };
}

/** Use a new `key` for each plan, so the question comes back. */
export function RatePlan({ shown }: { shown: Shown }) {
  const { status, send } = useSend(shown);
  const [down, setDown] = useState(false);
  const [other, setOther] = useState(false);
  const [comment, setComment] = useState('');

  if (status === 'sent') return <p className="rate muted">Gracias.</p>;
  return (
    <div className="rate">
      <div className="rate__ask">
        <span>¿Te sirvió esta recomendación?</span>
        <button type="button" className="icon-btn" aria-label="Sí" title="Sí" disabled={status === 'sending'} onClick={() => send({ kind: 'rating', useful: true })}>
          <ThumbUp />
        </button>
        <button
          type="button"
          className={`icon-btn ${down ? 'is-on' : ''}`}
          aria-label="No"
          title="No"
          aria-expanded={down}
          disabled={status === 'sending'}
          onClick={() => setDown(true)}
        >
          <ThumbDown />
        </button>
      </div>
      {down && !other && (
        <div className="chips" role="group" aria-label="¿Por qué no?">
          {REASONS.map(({ key, label }) => (
            <button
              key={key}
              type="button"
              className="chip"
              disabled={status === 'sending'}
              onClick={() => (key === 'other' ? setOther(true) : send({ kind: 'rating', useful: false, reason: key }))}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {other && (
        <form
          className="rate__comment"
          onSubmit={(e) => {
            e.preventDefault();
            send({ kind: 'rating', useful: false, reason: 'other', comment: comment.trim() || undefined });
          }}
        >
          <input
            type="text"
            value={comment}
            maxLength={280}
            onChange={(e) => setComment(e.target.value)}
            placeholder="¿Qué falló? Sin datos personales, por favor."
            aria-label="Qué falló"
          />
          <button type="submit" className="pill pill--sm" disabled={status === 'sending'}>
            Enviar
          </button>
        </form>
      )}
      {status === 'failed' && <p className="rate__error">No se pudo enviar. Intenta de nuevo.</p>}
      <p className="rate__privacy muted">{PRIVACY}</p>
    </div>
  );
}

/** Asks about the last plan of this browser, from the end of its trip time until 12 h later. In dev, asks at once
 *  about `currentPlanId` only. */
export function TripCheck({ currentPlanId }: { currentPlanId: string }) {
  const [trip, setTrip] = useState<Trip | null>(null);
  const plan = useRef(currentPlanId);
  plan.current = currentPlanId;

  useEffect(() => {
    // Keep the question on screen while the person answers. In dev, a new plan replaces it.
    const check = () =>
      setTrip((t) => {
        const due = dueTrip(Date.now(), undefined, DEV);
        if (!DEV) return t ?? due;
        const current = due?.shown.plan_id === plan.current ? due : null;
        // An answered plan has no due trip: keep it for the thanks.
        const answering = t?.shown.plan_id === plan.current && (!current || tripKey(current) === tripKey(t));
        return answering ? t : current;
      });
    check();
    const timer = setInterval(check, DEV ? DEV_CHECK_MS : CHECK_MS);
    return () => clearInterval(timer);
  }, []);

  if (!trip) return null;
  return <TripQuestion key={tripKey(trip)} trip={trip} onDone={() => setTrip(null)} />;
}

const tripKey = (t: Trip) => `${t.shown.plan_id}|${t.shown.dropoff_id}`;

function TripQuestion({ trip, onDone }: { trip: Trip; onDone: () => void }) {
  const [dock, setDock] = useState<DockAnswer | null>(null);
  const { status, send } = useSend(trip.shown);

  useEffect(() => {
    if (status !== 'sent') return;
    const timer = setTimeout(onDone, THANKS_MS);
    return () => clearTimeout(timer);
  }, [status]);

  const close = () => {
    markAnswered();
    onDone();
  };
  const answerDock = (a: DockAnswer) => (a === 'no_trip' ? send({ kind: 'trip', found_dock: a }, markAnswered) : setDock(a));

  return (
    <aside className="trip-check" aria-label="Tu último viaje">
      <button type="button" className="icon-btn trip-check__close" aria-label="No preguntar" onClick={close}>
        <Close />
      </button>
      {status === 'sent' ? (
        <p>Gracias. Tu respuesta nos ayuda a mejorar las predicciones.</p>
      ) : dock === null ? (
        <>
          <p>
            ¿Encontraste lugar para dejar la bici en <strong>{trip.dropoffName}</strong>?
          </p>
          <div className="chips">
            <button type="button" className="chip" disabled={status === 'sending'} onClick={() => answerDock('yes')}>
              Sí
            </button>
            <button type="button" className="chip" disabled={status === 'sending'} onClick={() => answerDock('no')}>
              No
            </button>
            <button type="button" className="chip" disabled={status === 'sending'} onClick={() => answerDock('no_trip')}>
              No hice el viaje
            </button>
          </div>
        </>
      ) : (
        <>
          <p>
            ¿Había bici en <strong>{trip.pickupName}</strong> cuando llegaste?
          </p>
          <div className="chips">
            {(['yes', 'no'] as const).map((bike) => (
              <button
                key={bike}
                type="button"
                className="chip"
                disabled={status === 'sending'}
                onClick={() => send({ kind: 'trip', found_dock: dock, found_bike: bike }, markAnswered)}
              >
                {bike === 'yes' ? 'Sí' : 'No'}
              </button>
            ))}
          </div>
        </>
      )}
      {status === 'failed' && <p className="rate__error">No se pudo enviar. Intenta de nuevo.</p>}
      {status !== 'sent' && <p className="rate__privacy muted">{PRIVACY}</p>}
    </aside>
  );
}
