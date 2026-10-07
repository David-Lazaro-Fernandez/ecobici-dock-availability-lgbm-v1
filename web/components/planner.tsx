'use client';

// The trip planner, on the skeleton of a-donde-ir's recommender: a full-height stage with the map under the top bar,
// a veil and a centred title until there is a start, and a dock with one search bar that slides to the foot once the
// start is set. One bar edits one end of the trip at a time (From, then To; the chips above it switch). A card at the
// top left lists where to drop the bike, best first. Data from ecobici.api; the map from trip-map.tsx.

import dynamic from 'next/dynamic';
import { type CSSProperties, type SyntheticEvent, type KeyboardEvent, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { type Candidate, type PlanResponse, type StationsResponse, useApi } from '@/lib/api';
import { type Suggestion, bbox, geocode, plain, searchStations } from '@/lib/places';
import { Close, Dock, Locate, Pin, Send, Sliders, Walk } from '@/components/icons';
import { FREE_STEPS } from '@/components/trip-map';

const TripMap = dynamic(() => import('@/components/trip-map'), { ssr: false });

const CDMX = { lat: 19.4178, lng: -99.1654 };
const REFRESH_MS = 60_000;
const RADII = [300, 500, 750, 1000];
const FAILURE_COSTS = [5, 7.5, 10];
const ONLINE_MIN_CHARS = 3;
const SUGGEST_WAIT_MS = 250;
const SUGGEST_LIMIT = 5;
// How much of the map the docked bar and the card cover (desktop), so the camera frames the rest.
const DOCK_OVERLAP = 170;
const CARD_WIDTH = 420;
const TZ = 'America/Mexico_City';
const clock = new Intl.DateTimeFormat('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: TZ });
const FREE_LEGEND = ['< 50 %', '50–80 %', '80–95 %', '≥ 95 %'];

type End = 'from' | 'to';
type Picked = { lat: number; lng: number; label: string; stationId?: string };

const pct = (p: number | null) => (p == null ? '—' : `${Math.round(p * 100)} %`);
const minutes = (m: number) => `${Math.max(1, Math.round(m))} min`;
const meters = (m: number) => (m < 950 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
const shortName = (name: string) => name.replace(/^CE-\d+\s*/, '');
// Some stations share a name ("Liverpool - Génova" twice): the code tells them apart.
const Code = ({ code }: { code: string }) => <span className="code">{code}</span>;
const whyNoBike = (s: { state: string; bikes: number | null }) =>
  s.state === 'unavailable' ? 'is out of service' : s.state === 'stale' ? 'is not reporting' : 'has no bikes right now';
const band = (p: number | null) => (p == null ? 'none' : String(FREE_STEPS.filter((s) => p >= s).length));

const PHONE = '(max-width: 700px)';
function usePhone() {
  return useSyncExternalStore(
    (notify) => {
      const q = window.matchMedia(PHONE);
      q.addEventListener('change', notify);
      return () => q.removeEventListener('change', notify);
    },
    () => window.matchMedia(PHONE).matches,
    () => false,
  );
}

function Best({ c, walkToPickup }: { c: Candidate; walkToPickup: number }) {
  return (
    <div className={`card__pick ${c.rank === 1 ? 'is-best' : ''}`}>
      <span className="card__rank">{c.rank}</span>
      <div className="card__pick-body">
        <strong>
          {shortName(c.name)} <Code code={c.code} />
        </strong>
        <span className="muted">
          Arrive ~{clock.format(new Date(c.arrive_at))} · ride {minutes(c.ride_min)} · then walk {meters(c.walk_m)}
          {c.expected_min != null && ` · ~${minutes(walkToPickup + c.expected_min)} expected`}
        </span>
      </div>
      <span className="card__chance">
        <i className={`swatch swatch--${band(c.p_free)}`} aria-hidden="true" />
        {pct(c.p_free)}
      </span>
    </div>
  );
}

export function Planner() {
  const phone = usePhone();
  const [start, setStart] = useState<Picked | null>(null);
  const [goal, setGoal] = useState<Picked | null>(null);
  const [editing, setEditing] = useState<End>('from');
  const [text, setText] = useState('');
  const [typing, setTyping] = useState(false);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [active, setActive] = useState(0);
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [menu, setMenu] = useState(false);
  const [cardOpen, setCardOpen] = useState(true);
  const [radius, setRadius] = useState(500);
  const [failure, setFailure] = useState(7.5);
  const [tick, setTick] = useState(0);
  const located = start !== null;

  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), REFRESH_MS);
    return () => clearInterval(t);
  }, []);

  const live = useApi<StationsResponse>('/v1/stations', useMemo(() => new URLSearchParams(), []), tick || null, 0);
  const stations = live.data?.stations ?? [];
  const box = useMemo(() => bbox(stations), [stations.length]);
  const near = start ?? CDMX;

  const planParams = useMemo(() => {
    if (!start || !goal) return null;
    const p = new URLSearchParams({ to_lat: String(goal.lat), to_lng: String(goal.lng), radius_m: String(radius), failure_min: String(failure) });
    if (start.stationId) p.set('from_station', start.stationId);
    else {
      p.set('from_lat', String(start.lat));
      p.set('from_lng', String(start.lng));
    }
    return p;
  }, [start, goal, radius, failure]);
  const plan = useApi<PlanResponse>('/v1/plan', planParams, tick || null);
  const result = planParams ? plan.data : null;
  const ranked = result?.candidates.filter((c) => c.rank != null) ?? [];
  const walkToPickup = result?.pickup.walk_min ?? 0;
  const showCard = Boolean(start && goal && cardOpen && (result || plan.loading));

  // Suggestions for the text in the bar: stations at once, addresses after a pause.
  useEffect(() => {
    if (!typing) return setSuggestions([]);
    const local = searchStations(stations, text, 3);
    setSuggestions(local);
    setActive(0);
    if (plain(text).length < ONLINE_MIN_CHARS) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      geocode(text, near, box, SUGGEST_LIMIT, ctrl.signal)
        .then((remote) => {
          const seen = new Set(local.map((s) => plain(s.name)));
          setSuggestions([...local, ...remote.filter((s) => !seen.has(plain(s.name)))].slice(0, SUGGEST_LIMIT));
        })
        .catch(() => {
          if (!ctrl.signal.aborted) setNotice('Address search is not reachable right now. Station names still work.');
        });
    }, SUGGEST_WAIT_MS);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [text, typing, stations.length, box, near.lat, near.lng]);

  function set(end: End, p: Picked | null) {
    if (end === 'from') setStart(p);
    else setGoal(p);
    setText('');
    setTyping(false);
    setSuggestions([]);
    setNotice('');
    setCardOpen(true);
    // After the start, the bar asks for the destination.
    setEditing(end === 'from' && !goal ? 'to' : end);
  }

  function choose(s: Suggestion) {
    set(editing, { lat: s.lat, lng: s.lng, label: s.name, stationId: s.stationId });
  }

  async function search(e: SyntheticEvent<HTMLFormElement>) {
    e.preventDefault();
    if (suggestions[active]) return choose(suggestions[active]);
    if (!text.trim()) return;
    setBusy(true);
    try {
      const [first] = await geocode(text, near, box, 1);
      if (first) choose(first);
      else setNotice('No match inside the Ecobici area. Try adding the neighbourhood (colonia).');
    } catch {
      setNotice('Address search is not reachable right now. Station names still work.');
    } finally {
      setBusy(false);
    }
  }

  function locate() {
    if (!navigator.geolocation) return setNotice('This browser cannot share its location.');
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setBusy(false);
        set('from', { lat: p.coords.latitude, lng: p.coords.longitude, label: 'My location' });
      },
      () => {
        setBusy(false);
        setNotice('Location is blocked or unavailable. Type an address instead.');
      },
      { enableHighAccuracy: true, timeout: 10_000 },
    );
  }

  function keys(e: KeyboardEvent<HTMLInputElement>) {
    if (!suggestions.length) return;
    if (e.key === 'ArrowDown') setActive((a) => Math.min(a + 1, suggestions.length - 1));
    else if (e.key === 'ArrowUp') setActive((a) => Math.max(a - 1, 0));
    else if (e.key === 'Escape') setSuggestions([]);
    else return;
    e.preventDefault();
  }

  const captured = live.data ? new Date(live.data.captured_at) : null;
  const ageMin = captured ? (Date.now() - captured.getTime()) / 60_000 : null;
  const status = live.error
    ? live.error
    : captured
      ? `Live · stations read at ${clock.format(captured)}${ageMin! > 10 ? ` (${Math.round(ageMin!)} min ago)` : ''}`
      : 'Loading live stations…';

  const context = !start
    ? ''
    : !goal
      ? 'Now, where are you going? Type it, or double click the map.'
      : plan.error
        ? plan.error
        : !result
          ? 'Planning…'
          : ranked.length === 0
            ? 'No station near the destination can be recommended right now.'
            : `${result.requested ? `No bikes to take at ${shortName(result.requested.name)}. ` : ''}Take a bike at ${shortName(result.pickup.name)}${result.pickup.walk_m > 0 ? ` (${meters(result.pickup.walk_m)} away)` : ''} · drop it at ${shortName(ranked[0].name)}: ${pct(ranked[0].p_free)} chance of a free dock`;

  const inset = {
    top: 0,
    bottom: located ? DOCK_OVERLAP : 0,
    left: showCard && !phone ? CARD_WIDTH + 24 : 0,
    right: 0,
  };

  const menuBox = (
    <div className={`menu ${menu ? 'is-open' : ''}`} aria-hidden={!menu}>
      <div className="menu__row">
        <span className="menu__label">
          <Walk /> Max walk to your destination
        </span>
        <div className="chips" role="radiogroup" aria-label="Max walk">
          {RADII.map((r) => (
            <button key={r} type="button" role="radio" aria-checked={radius === r} className={`chip ${radius === r ? 'is-on' : ''}`} onClick={() => setRadius(r)}>
              {meters(r)}
            </button>
          ))}
        </div>
      </div>
      <div className="menu__row">
        <span className="menu__label">
          <Dock /> Minutes lost if the station is full
        </span>
        <div className="chips" role="radiogroup" aria-label="Failure cost">
          {FAILURE_COSTS.map((f) => (
            <button key={f} type="button" role="radio" aria-checked={failure === f} className={`chip ${failure === f ? 'is-on' : ''}`} onClick={() => setFailure(f)}>
              {f} min
            </button>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <>
      <header className="topbar">
        <span className="topbar__brand">Dock finder</span>
        <span className={`topbar__status ${live.error ? 'is-error' : ageMin != null && ageMin > 10 ? 'is-old' : ''}`}>{status}</span>
      </header>

      <section className={`stage ${located ? 'is-located' : ''}`} style={{ '--card-width': `${CARD_WIDTH}px` } as CSSProperties}>
        <div className="stage__map">
          <TripMap
            center={CDMX}
            stations={stations}
            start={start}
            goal={goal}
            pickup={result?.pickup ?? null}
            candidates={result?.candidates ?? []}
            radiusM={radius}
            inset={inset}
            onPickGoal={(p) => set('to', { ...p, label: 'Point on the map' })}
          />
        </div>
        {/* Without a start, the veil covers the map and blocks its clicks. */}
        <div className="stage__glass" aria-hidden="true" />

        {!located && <h1 className="stage__title">Where are you riding to?</h1>}

        {showCard && (
          <aside className="card" aria-label="Where to drop the bike" aria-busy={plan.loading}>
            <div className="card__head">
              <div>
                <strong>Where to drop the bike</strong>
                <span className="muted">
                  {result ? `${result.candidates.length} stations within ${meters(result.radius_m)} of your destination` : 'Planning…'}
                </span>
              </div>
              <button type="button" className="icon-btn" aria-label="Close" onClick={() => setCardOpen(false)}>
                <Close />
              </button>
            </div>
            {!result ? (
              <ul className="card__list">
                {[0, 1, 2, 3].map((i) => (
                  <li key={i} className="card__skeleton" aria-hidden="true">
                    <span />
                    <span />
                    <span />
                  </li>
                ))}
              </ul>
            ) : (
              <>
                <div className="card__pickup">
                  <span className="dot dot--start" aria-hidden="true" />
                  <p>
                    {result.requested && (
                      <span className="card__warn">
                        {shortName(result.requested.name)} <Code code={result.requested.code} /> {whyNoBike(result.requested)}.
                        The nearest station with bikes is:
                      </span>
                    )}
                    Take a bike at{' '}
                    <strong>
                      {shortName(result.pickup.name)} <Code code={result.pickup.code} />
                    </strong>
                    <span className="muted">
                      {result.pickup.walk_m > 0 ? `${meters(result.pickup.walk_m)} walk (${minutes(result.pickup.walk_min)}) · ` : ''}
                      {result.pickup.bikes ?? '—'} bikes now
                    </span>
                  </p>
                </div>
                {ranked.slice(0, 2).map((c) => (
                  <Best key={c.id} c={c} walkToPickup={walkToPickup} />
                ))}
                <ul className="card__list">
                  {result.candidates
                    .filter((c) => !(c.rank && c.rank <= 2))
                    .map((c) => (
                      <li key={c.id} className={c.recommendable ? '' : 'is-muted'}>
                        <span className="card__name">
                          {c.rank ? `${c.rank}. ` : ''}
                          {shortName(c.name)} <Code code={c.code} />
                          <span className="muted">
                            {c.recommendable
                              ? `${meters(c.walk_m)} to destination · ${c.docks ?? '—'} free now · ride ${minutes(c.ride_min)}`
                              : c.state === 'stale'
                                ? 'Not reporting: not recommended'
                                : 'Out of service'}
                          </span>
                        </span>
                        <span className="card__chance">
                          <i className={`swatch swatch--${band(c.p_free)}`} aria-hidden="true" />
                          {pct(c.p_free)}
                        </span>
                      </li>
                    ))}
                </ul>
                <div className="card__legend" aria-label="Legend">
                  <span>Chance of a free dock on arrival:</span>
                  {FREE_LEGEND.map((l, i) => (
                    <span key={l}>
                      <i className={`swatch swatch--${i}`} aria-hidden="true" /> {l}
                    </span>
                  ))}
                </div>
              </>
            )}
          </aside>
        )}

        {phone && <div className={`menu__scrim ${menu ? 'is-open' : ''}`} aria-hidden="true" onClick={() => setMenu(false)} />}
        <div className="dock">
          {menuBox}
          {located && (
            <div className="dock__ends" role="group" aria-label="Trip">
              <button type="button" className={`end ${editing === 'from' ? 'is-on' : ''}`} onClick={() => setEditing('from')}>
                <span className="dot dot--start" aria-hidden="true" />
                <span className="end__text">
                  <small>From</small>
                  {start!.label}
                </span>
              </button>
              <button type="button" className={`end ${editing === 'to' ? 'is-on' : ''}`} onClick={() => setEditing('to')}>
                <span className="dot dot--goal" aria-hidden="true" />
                <span className="end__text">
                  <small>To</small>
                  {goal?.label ?? 'Choose a destination'}
                </span>
              </button>
            </div>
          )}
          {located && context && (
            <div className="dock__context">
              <span>{context}</span>
              {start && goal && result && !cardOpen && (
                <button type="button" className="pill pill--sm" onClick={() => setCardOpen(true)}>
                  Show stations
                </button>
              )}
            </div>
          )}
          <div className="ask-box">
            {suggestions.length > 0 && (
              <ul className={`suggest ${located ? '' : 'suggest--down'}`} role="listbox" id="suggest" aria-label="Suggestions">
                {suggestions.map((s, i) => (
                  <li key={`${s.lat},${s.lng},${s.name}`} role="option" aria-selected={i === active}>
                    <button
                      type="button"
                      className={`suggest__item ${i === active ? 'is-active' : ''}`}
                      onMouseDown={(e) => e.preventDefault()}
                      onMouseEnter={() => setActive(i)}
                      onClick={() => choose(s)}
                    >
                      <span className="suggest__icon">{s.stationId ? <Dock /> : <Pin />}</span>
                      <span className="suggest__text">
                        <strong>{s.name}</strong> {s.context}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            <form className="ask" onSubmit={search}>
              <button
                type="button"
                className={`ask__icon ${menu ? 'is-on' : ''}`}
                aria-label="Options: walking distance and failure cost"
                aria-expanded={menu}
                onClick={() => setMenu((m) => !m)}
              >
                <Sliders />
              </button>
              <input
                className="ask__input"
                type="text"
                value={text}
                onChange={(e) => {
                  setText(e.target.value);
                  setTyping(true);
                  setMenu(false);
                  setNotice('');
                }}
                onKeyDown={keys}
                onBlur={() => setSuggestions([])}
                role="combobox"
                aria-expanded={suggestions.length > 0}
                aria-controls="suggest"
                aria-autocomplete="list"
                autoComplete="off"
                aria-label={editing === 'from' ? 'Where you start' : 'Where you are going'}
                placeholder={
                  editing === 'from'
                    ? located
                      ? 'Change the start: street, place or station'
                      : 'Where do you start? Street, place or station'
                    : 'Where are you going? Street, place or station'
                }
              />
              {editing === 'from' && (
                <button type="button" className="ask__locate" onClick={locate} disabled={busy}>
                  <Locate />
                  <span>My location</span>
                </button>
              )}
              <button type="submit" className="ask__send" aria-label="Search" disabled={busy || !text.trim()}>
                <Send />
              </button>
            </form>
          </div>
          {(!located || notice) && (
            <p className="stage__hint">{notice || 'Type where you start, or use your location. Then choose where you are going.'}</p>
          )}
        </div>
      </section>
    </>
  );
}
