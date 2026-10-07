'use client';

// The trip planner, on the a-donde-ir recommender skeleton: stage, dock with one search bar, and a card with the
// stations. The search bar edits one end of the trip at a time (From, then To).

import dynamic from 'next/dynamic';
import { type CSSProperties, type SyntheticEvent, type KeyboardEvent, useEffect, useMemo, useState, useSyncExternalStore } from 'react';
import { type Candidate, type PlanResponse, type StationsResponse, useApi } from '@/lib/api';
import { type PlacesFile, type Suggestion, bbox, buildIndex, cachedOnline, geocode, loadPlaces, merge, plain, searchPlaces } from '@/lib/places';
import { Clock, Close, Dock, Locate, Pin, Send, Sliders, Walk } from '@/components/icons';
import { type SortKey, sortCandidates } from '@/lib/sort';
import { type Leg, useTripRoutes } from '@/lib/routes';
import { FREE_STEPS } from '@/components/trip-map';

const TripMap = dynamic(() => import('@/components/trip-map'), { ssr: false });

const CDMX = { lat: 19.4178, lng: -99.1654 };
const REFRESH_MS = 60_000;
const RADII = [300, 500, 750, 1000];
const FAILURE_COSTS = [5, 7.5, 10];
const ONLINE_MIN_CHARS = 3;
const SUGGEST_WAIT_MS = 250;
const SUGGEST_LIMIT = 5;
// The map area under the docked bar and the card (desktop). The camera frames the rest.
const DOCK_OVERLAP = 170;
const CARD_WIDTH = 420;
const TZ = 'America/Mexico_City';
const clock = new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: TZ });
const FREE_LEGEND = ['< 50 %', '50–80 %', '80–95 %', '≥ 95 %'];

type End = 'from' | 'to';
type Picked = { lat: number; lng: number; label: string; stationId?: string };

const pct = (p: number | null) => (p == null ? '—' : `${Math.round(p * 100)} %`);
const minutes = (m: number) => `${Math.max(1, Math.round(m))} min`;
const meters = (m: number) => (m < 950 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
const shortName = (name: string) => name.replace(/^CE-\d+\s*/, '');
// Some stations have the same name ("Liverpool - Génova" twice). The code tells them apart.
const Code = ({ code }: { code: string }) => <span className="code">{code}</span>;
const whyNoBike = (s: { state: string }) =>
  s.state === 'unavailable' ? 'está fuera de servicio' : s.state === 'stale' ? 'no envía datos recientes' : 'no tiene bicis ahora';
const band = (p: number | null) => (p == null ? 'none' : String(FREE_STEPS.filter((s) => p >= s).length));
// Show the risk of an empty pickup only when it can change the decision.
const EMPTY_RISK_SHOWN = 0.1;

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

const SORTS: { key: SortKey; label: string; hint: string; icon: () => React.JSX.Element }[] = [
  { key: 'time', label: 'Tiempo', hint: 'Ordenar por tiempo de viaje', icon: Clock },
  { key: 'walk', label: 'Caminar', hint: 'Ordenar por distancia a pie al destino', icon: Walk },
  { key: 'free', label: 'Disponibilidad', hint: 'Ordenar por probabilidad de lugar libre', icon: Dock },
];

function routeText(legs: Leg[]) {
  const bike = legs.find((l) => l.mode === 'bike');
  const walk = legs.at(-1)?.mode === 'walk' ? legs.at(-1) : undefined;
  const approx = (l: Leg) => (l.routed ? '' : '~');
  const parts = [];
  if (bike) parts.push(`En bici ${approx(bike)}${meters(bike.distance_m)}${bike.duration_min != null ? ` (${minutes(bike.duration_min)})` : ''}`);
  if (walk) parts.push(`a pie ${approx(walk)}${meters(walk.distance_m)}`);
  return parts.join(' · ');
}

function Row({ c, selected, route, onSelect }: { c: Candidate; selected: boolean; route: string; onSelect: () => void }) {
  if (!c.recommendable)
    return (
      <li className="row is-muted">
        <span className="row__rank" aria-hidden="true" />
        <span className="row__body">
          <strong>
            {shortName(c.name)} <Code code={c.code} />
          </strong>
          <span className="muted">{c.state === 'stale' ? 'Sin datos recientes' : 'Fuera de servicio'}</span>
        </span>
      </li>
    );
  return (
    <li>
      <button type="button" className={`row ${selected ? 'is-selected' : ''} ${c.rank === 1 ? 'is-best' : ''}`} aria-pressed={selected} onClick={onSelect}>
        <span className="row__rank">{c.rank}</span>
        <span className="row__body">
          <strong>
            {shortName(c.name)} <Code code={c.code} />
            {c.rank === 1 && <span className="row__tag">Mejor</span>}
          </strong>
          <span className="muted">
            Llegas {clock.format(new Date(c.arrive_at))} · {meters(c.walk_m)} a pie
          </span>
          {selected && route && <span className="row__route">{route}</span>}
        </span>
        <span className="card__chance">
          <i className={`swatch swatch--${band(c.p_free)}`} aria-hidden="true" />
          {pct(c.p_free)}
        </span>
      </button>
    </li>
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
  const [sortBy, setSortBy] = useState<SortKey>('time');
  // The drop-off picked in the list or on the map, for one search only.
  const [picked, setPicked] = useState<{ searchKey: string; id: string } | null>(null);
  const [tick, setTick] = useState(0);
  const located = start !== null;

  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), REFRESH_MS);
    return () => clearInterval(t);
  }, []);

  const live = useApi<StationsResponse>('/v1/stations', useMemo(() => new URLSearchParams(), []), tick || null, 0);
  const stations = live.data?.stations ?? [];
  const box = useMemo(() => bbox(stations), [stations.length]);
  const [placesFile, setPlacesFile] = useState<PlacesFile | null>(null);
  useEffect(() => {
    loadPlaces().then(setPlacesFile);
  }, []);
  const index = useMemo(() => buildIndex(placesFile, stations), [placesFile, stations.length]);
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
  const searchKey = planParams ? String(planParams) : '';
  const dropoff = ranked.find((c) => picked?.searchKey === searchKey && c.id === picked.id) ?? ranked[0] ?? null;
  const legs = useTripRoutes(start, result?.pickup ?? null, dropoff, goal);
  const selectDropoff = (id: string) => {
    if (ranked.some((c) => c.id === id)) setPicked({ searchKey, id });
  };
  const showCard = Boolean(start && goal && cardOpen && (result || plan.loading));

  // Suggestions: the local index and saved answers at once, Photon after a pause.
  useEffect(() => {
    if (!typing) return setSuggestions([]);
    const local = searchPlaces(index, text, near, SUGGEST_LIMIT);
    setSuggestions(merge(text, local, cachedOnline(text, near, SUGGEST_LIMIT), SUGGEST_LIMIT));
    setActive(0);
    if (plain(text).length < ONLINE_MIN_CHARS) return;
    const ctrl = new AbortController();
    const t = setTimeout(() => {
      geocode(text, near, box, SUGGEST_LIMIT, ctrl.signal)
        .then((online) => setSuggestions(merge(text, local, online, SUGGEST_LIMIT)))
        .catch(() => {
          if (!ctrl.signal.aborted) setNotice('La búsqueda de direcciones no responde. Los lugares conocidos sí funcionan.');
        });
    }, SUGGEST_WAIT_MS);
    return () => {
      clearTimeout(t);
      ctrl.abort();
    };
  }, [text, typing, index, box, near.lat, near.lng]);

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
      else setNotice('No hay resultados en la zona de Ecobici. Agrega la colonia.');
    } catch {
      setNotice('La búsqueda de direcciones no responde. Los lugares conocidos sí funcionan.');
    } finally {
      setBusy(false);
    }
  }

  function locate() {
    if (!navigator.geolocation) return setNotice('Este navegador no comparte la ubicación.');
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setBusy(false);
        set('from', { lat: p.coords.latitude, lng: p.coords.longitude, label: 'Mi ubicación' });
      },
      () => {
        setBusy(false);
        setNotice('La ubicación está bloqueada o no está disponible. Escribe una dirección.');
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
      ? `En vivo · estaciones leídas a las ${clock.format(captured)}${ageMin! > 10 ? ` (hace ${Math.round(ageMin!)} min)` : ''}`
      : 'Cargando estaciones…';

  const context = !start
    ? ''
    : !goal
      ? 'Ahora, ¿a dónde vas? Escríbelo o haz doble clic en el mapa.'
      : plan.error
        ? plan.error
        : !result
          ? 'Calculando…'
          : !dropoff
            ? 'Ahora no se puede recomendar ninguna estación cerca del destino.'
            : `Toma la bici en ${shortName(result.pickup.name)} y déjala en ${shortName(dropoff.name)}: ${pct(dropoff.p_free)} de encontrar lugar`;

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
          <Walk /> Máximo a pie hasta tu destino
        </span>
        <div className="chips" role="radiogroup" aria-label="Máximo a pie">
          {RADII.map((r) => (
            <button key={r} type="button" role="radio" aria-checked={radius === r} className={`chip ${radius === r ? 'is-on' : ''}`} onClick={() => setRadius(r)}>
              {meters(r)}
            </button>
          ))}
        </div>
      </div>
      <div className="menu__row">
        <span className="menu__label">
          <Dock /> Minutos perdidos si la estación está llena
        </span>
        <div className="chips" role="radiogroup" aria-label="Minutos perdidos">
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
        <span className="topbar__brand">Lugar libre</span>
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
            legs={legs}
            selectedId={dropoff?.id ?? null}
            onSelect={selectDropoff}
            inset={inset}
            onPickGoal={(p) => set('to', { ...p, label: 'Punto en el mapa' })}
          />
        </div>
        {/* Without a start, the veil covers the map and blocks its clicks. */}
        <div className="stage__glass" aria-hidden="true" />

        {!located && <h1 className="stage__title">¿A dónde vas en bici?</h1>}

        {showCard && (
          <aside className="card" aria-label="Dónde dejar la bici" aria-busy={plan.loading}>
            <div className="card__head">
              <div>
                <strong>Dónde dejar la bici</strong>
                <span className="muted">
                  {result ? `${result.candidates.length} estaciones a ${meters(result.radius_m)} o menos de tu destino` : 'Calculando…'}
                </span>
              </div>
              <button type="button" className="icon-btn" aria-label="Cerrar" onClick={() => setCardOpen(false)}>
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
                        {shortName(result.requested.name)} {whyNoBike(result.requested)}.
                      </span>
                    )}
                    Toma la bici en <strong>{shortName(result.pickup.name)}</strong> <Code code={result.pickup.code} />
                    <span className="muted">
                      {result.pickup.walk_m > 0 ? `A ${meters(result.pickup.walk_m)} · ` : ''}
                      {result.pickup.bikes ?? '—'} bicis
                      {(result.pickup.p_empty_at_arrival ?? 0) >= EMPTY_RISK_SHOWN &&
                        ` · ${pct(result.pickup.p_empty_at_arrival)} de que se acaben antes de que llegues`}
                    </span>
                  </p>
                </div>
                <div className="sort" role="radiogroup" aria-label="Ordenar estaciones">
                  {SORTS.map(({ key, label, hint, icon: Icon }) => (
                    <button
                      key={key}
                      type="button"
                      role="radio"
                      aria-checked={sortBy === key}
                      aria-label={hint}
                      title={hint}
                      className={`sort__btn ${sortBy === key ? 'is-on' : ''}`}
                      onClick={() => setSortBy(key)}
                    >
                      <Icon />
                      <span>{label}</span>
                    </button>
                  ))}
                </div>
                <ul className="card__list">
                  {sortCandidates(result.candidates, sortBy).map((c) => (
                    <Row
                      key={c.id}
                      c={c}
                      selected={c.id === dropoff?.id}
                      route={c.id === dropoff?.id ? routeText(legs) : ''}
                      onSelect={() => selectDropoff(c.id)}
                    />
                  ))}
                </ul>
                <div className="card__legend">
                  <p className="card__legend-title">Probabilidad de lugar libre al llegar</p>
                  <div className="card__legend-items">
                    {FREE_LEGEND.map((l, i) => (
                      <span key={l}>
                        <i className={`swatch swatch--${i}`} aria-hidden="true" /> {l}
                      </span>
                    ))}
                  </div>
                </div>
              </>
            )}
          </aside>
        )}

        {phone && <div className={`menu__scrim ${menu ? 'is-open' : ''}`} aria-hidden="true" onClick={() => setMenu(false)} />}
        <div className="dock">
          {menuBox}
          {located && (
            <div className="dock__ends" role="group" aria-label="Viaje">
              <button type="button" className={`end ${editing === 'from' ? 'is-on' : ''}`} onClick={() => setEditing('from')}>
                <span className="dot dot--start" aria-hidden="true" />
                <span className="end__text">
                  <small>Desde</small>
                  {start!.label}
                </span>
              </button>
              <button type="button" className={`end ${editing === 'to' ? 'is-on' : ''}`} onClick={() => setEditing('to')}>
                <span className="dot dot--goal" aria-hidden="true" />
                <span className="end__text">
                  <small>Hasta</small>
                  {goal?.label ?? 'Elige un destino'}
                </span>
              </button>
            </div>
          )}
          {located && context && (
            <div className="dock__context">
              <span>{context}</span>
              {start && goal && result && !cardOpen && (
                <button type="button" className="pill pill--sm" onClick={() => setCardOpen(true)}>
                  Ver estaciones
                </button>
              )}
            </div>
          )}
          <div className="ask-box">
            {suggestions.length > 0 && (
              <ul className={`suggest ${located ? '' : 'suggest--down'}`} role="listbox" id="suggest" aria-label="Sugerencias">
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
                aria-label="Opciones: distancia a pie y minutos perdidos"
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
                aria-label={editing === 'from' ? 'Desde dónde sales' : 'A dónde vas'}
                placeholder={
                  editing === 'from'
                    ? located
                      ? 'Cambia el punto de partida: calle, lugar o estación'
                      : '¿Desde dónde sales? Calle, lugar o estación'
                    : '¿A dónde vas? Calle, lugar o estación'
                }
              />
              {editing === 'from' && (
                <button type="button" className="ask__locate" onClick={locate} disabled={busy}>
                  <Locate />
                  <span>Mi ubicación</span>
                </button>
              )}
              <button type="submit" className="ask__send" aria-label="Buscar" disabled={busy || !text.trim()}>
                <Send />
              </button>
            </form>
          </div>
          {(!located || notice) && (
            <p className="stage__hint">{notice || 'Escribe desde dónde sales o usa tu ubicación. Luego elige a dónde vas.'}</p>
          )}
        </div>
      </section>
    </>
  );
}
