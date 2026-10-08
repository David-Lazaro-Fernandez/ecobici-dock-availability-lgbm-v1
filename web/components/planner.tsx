'use client';

// The trip planner, on the a-donde-ir recommender skeleton: stage, dock with the search, and a card with the
// stations. On a desktop, one search bar edits one end of the trip at a time (From, then To). On a phone, a form
// has one input for each end.

import dynamic from 'next/dynamic';
import { type CSSProperties, type ReactNode, type SyntheticEvent, type KeyboardEvent, useEffect, useMemo, useRef, useState } from 'react';
import { usePhone } from '@/lib/phone';
import { Drawer, type DrawerOptions } from '@/components/drawer';
import { type Candidate, type PlanResponse, type StationsResponse, useApi } from '@/lib/api';
import { type PlacesFile, type Suggestion, bbox, buildIndex, cachedOnline, geocode, loadPlaces, merge, plain, searchPlaces } from '@/lib/places';
import { Bike, Clock, Close, Dock, Locate, More, Pin, Send, Sliders, Walk } from '@/components/icons';
import { type SortKey, sortCandidates } from '@/lib/sort';
import { type Leg, useTripRoutes } from '@/lib/routes';
import { FREE_LEGEND, pct, sharedNames, shortName } from '@/lib/format';
import { FREE_STEPS } from '@/components/trip-map';
import { RatePlan, TripCheck } from '@/components/feedback';
import { Help } from '@/components/help';
import type { Shown } from '@/lib/feedback';
import { saveTrip } from '@/lib/trip';
import { type Messages, useLang, useMessages } from '@/lib/i18n';
import { LangSwitch } from '@/components/lang-switch';

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
// The phone trip bar and its margin, over the top of the map.
const PHONE_TRIP_BAR_PX = 64;
const TZ = 'America/Mexico_City';
// In prod, the status shows only when the station data is old or missing.
const DEV = process.env.NODE_ENV === 'development';
const clockFor = (locale: string) => new Intl.DateTimeFormat(locale, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: TZ });

type End = 'from' | 'to';
type Picked = { lat: number; lng: number; label: string; stationId?: string };

const minutes = (m: number) => `${Math.max(1, Math.round(m))} min`;
const meters = (m: number) => (m < 950 ? `${Math.round(m / 10) * 10} m` : `${(m / 1000).toFixed(1)} km`);
// Some stations have the same name ("Liverpool - Génova" twice). Show the code only to tell those apart.
const Code = ({ code, shown }: { code: string; shown: boolean }) => (shown ? <span className="code">{code}</span> : null);
const whyNoBike = (s: { state: string }, t: Messages) =>
  s.state === 'unavailable' ? t.whyNoBike.unavailable : s.state === 'stale' ? t.whyNoBike.stale : t.whyNoBike.empty;
// The ranking uses the arrival at the destination, so the row shows that time, not the arrival at the station.
const atDestination = (c: Candidate) => new Date(new Date(c.arrive_at).getTime() + c.walk_min * 60_000);
const band = (p: number | null) => (p == null ? 'none' : String(FREE_STEPS.filter((s) => p >= s).length));
// Show the risk of an empty pickup only when it can change the decision.
const EMPTY_RISK_SHOWN = 0.1;
const ROWS_FOLDED = 2;
// Captures arrive every 2 min. Older data is not live.
const OLD_AFTER_MIN = 10;

// The card fits above the dock, and the phone trip bar fits left of the language switch. Their sizes change with
// the content and the language. The element must stay mounted.
function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    if (!ref.current) return;
    const observer = new ResizeObserver(([entry]) =>
      setSize({ width: entry.borderBoxSize[0].inlineSize, height: entry.borderBoxSize[0].blockSize }),
    );
    observer.observe(ref.current);
    return () => observer.disconnect();
  }, []);
  return [ref, size] as const;
}

// The card on a desktop, the drawer on a phone, with the same content.
function CardShell({ drawer, label, busy, children }: { drawer: false | DrawerOptions; label: string; busy: boolean; children: ReactNode }) {
  if (drawer)
    return (
      <Drawer {...drawer} label={label} busy={busy}>
        {children}
      </Drawer>
    );
  return (
    <aside className="card" aria-label={label} aria-busy={busy}>
      {children}
    </aside>
  );
}

const SORTS: { key: SortKey; icon: () => React.JSX.Element }[] = [
  { key: 'time', icon: Clock },
  { key: 'walk', icon: Walk },
  { key: 'free', icon: Dock },
];

// The icon tells the kind of value. The label is for the tooltip and for screen readers.
function Fact({ icon: Icon, label, children }: { icon: () => React.JSX.Element; label: string; children: React.ReactNode }) {
  return (
    <span className="fact" title={label}>
      <Icon />
      <span className="sr-only">{label}: </span>
      {children}
    </span>
  );
}

// The row facts already show the walk, so the selected row adds only the bike leg.
function bikeText(legs: Leg[]) {
  const bike = legs.find((l) => l.mode === 'bike');
  if (!bike) return '';
  const approx = bike.routed ? '' : '~';
  return `${approx}${meters(bike.distance_m)}${bike.duration_min != null ? ` · ${minutes(bike.duration_min)}` : ''}`;
}

function Row({ c, selected, bike, withCode, onSelect }: { c: Candidate; selected: boolean; bike: string; withCode: boolean; onSelect: () => void }) {
  const t = useMessages();
  if (!c.recommendable)
    return (
      <li className="row is-muted">
        <span className="row__rank" aria-hidden="true" />
        <span className="row__body">
          <strong>
            {shortName(c.name)} <Code code={c.code} shown={withCode} />
          </strong>
          <span className="muted">{c.state === 'stale' ? t.stationState.stale : t.stationState.unavailable}</span>
        </span>
      </li>
    );
  return (
    <li>
      <button type="button" className={`row ${selected ? 'is-selected' : ''} ${c.rank === 1 ? 'is-best' : ''}`} aria-pressed={selected} onClick={onSelect}>
        <span className="row__rank">{c.rank}</span>
        <span className="row__body">
          <strong>
            {shortName(c.name)} <Code code={c.code} shown={withCode} />
            {c.rank === 1 && <span className="row__tag">{t.planner.best}</span>}
          </strong>
          <span className="facts muted">
            <Fact icon={Clock} label={t.planner.arriveAtGoal}>
              {clockFor(t.locale).format(atDestination(c))}
            </Fact>
            <Fact icon={Walk} label={t.planner.walkToGoal}>
              {meters(c.walk_m)}
            </Fact>
            <Fact icon={Dock} label={t.planner.docksNow}>
              {t.planner.docksFree(String(c.docks ?? '—'))}
            </Fact>
          </span>
          {selected && bike && (
            <span className="facts row__route">
              <Fact icon={Bike} label={t.planner.byBike}>
                {bike}
              </Fact>
            </span>
          )}
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
  const [dockRef, dockSize] = useSize<HTMLDivElement>();
  const [cornerRef, cornerSize] = useSize<HTMLDivElement>();
  // Phone only: the stations drawer and the screen to change the trip ends.
  const [drawerOpen, setDrawerOpen] = useState(false);
  // One closed height for each search: a later change (the selected row gets the bike line) must not move the map.
  const [drawerPeek, setDrawerPeek] = useState({ searchKey: '', px: 0 });
  const [planning, setPlanning] = useState(false);
  const lang = useLang();
  const t = useMessages();
  const clock = useMemo(() => clockFor(t.locale), [t.locale]);
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
  // The search whose full list is open. A new search folds the list again.
  const [unfolded, setUnfolded] = useState('');
  const [tick, setTick] = useState(0);
  const located = start !== null;
  // On a phone, the map shows only when the trip has both ends. Until then, or when the person taps the trip bar
  // to change an end, the form stays in the middle.
  const docked = phone ? Boolean(start && goal) && !planning : located;
  const withDrawer = phone && docked;
  const toInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!menu) return;
    const close = (e: globalThis.KeyboardEvent) => e.key === 'Escape' && setMenu(false);
    window.addEventListener('keydown', close);
    return () => window.removeEventListener('keydown', close);
  }, [menu]);

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
  const index = useMemo(
    () => buildIndex(placesFile, stations, { station: t.places.station, kind: (k) => t.places.kinds[k] ?? k }),
    [placesFile, stations.length, t],
  );
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
  const planId = useMemo(() => (searchKey ? crypto.randomUUID() : ''), [searchKey]);
  const shown: Shown | null =
    result && dropoff
      ? {
          plan_id: planId,
          captured_at: result.captured_at,
          pickup_id: result.pickup.id,
          dropoff_id: dropoff.id,
          rank: dropoff.rank,
          arrive_at: dropoff.arrive_at,
          p_free: dropoff.p_free,
          p_empty_at_arrival: result.pickup.p_empty_at_arrival,
        }
      : null;
  useEffect(() => {
    if (shown) saveTrip({ shown, pickupName: shortName(result!.pickup.name), dropoffName: shortName(dropoff!.name) });
  }, [planId, shown?.captured_at, shown?.dropoff_id]);
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
    const timer = setTimeout(() => {
      geocode(text, near, box, SUGGEST_LIMIT, ctrl.signal)
        .then((online) => setSuggestions(merge(text, local, online, SUGGEST_LIMIT)))
        .catch(() => {
          if (!ctrl.signal.aborted) setNotice(t.planner.searchDown);
        });
    }, SUGGEST_WAIT_MS);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [text, typing, index, box, near.lat, near.lng, t]);

  function set(end: End, p: Picked | null) {
    if (end === 'from') setStart(p);
    else setGoal(p);
    setText('');
    setTyping(false);
    setSuggestions([]);
    setNotice('');
    setCardOpen(true);
    setPlanning(false);
    setDrawerOpen(false);
    // After the start, the bar asks for the destination.
    const next = end === 'from' && !goal ? 'to' : end;
    setEditing(next);
    if (phone) {
      if (next === 'to' && end === 'from') toInput.current?.focus();
      else if (document.activeElement instanceof HTMLElement) document.activeElement.blur();
    }
  }

  // Back to the start screen, without a start or a destination.
  function resetTrip() {
    setStart(null);
    setGoal(null);
    setText('');
    setTyping(false);
    setSuggestions([]);
    setNotice('');
    setMenu(false);
    setPlanning(false);
    setDrawerOpen(false);
    setPicked(null);
    setUnfolded('');
    setEditing('from');
  }

  function choose(s: Suggestion) {
    set(editing, { lat: s.lat, lng: s.lng, label: s.name, stationId: s.stationId });
  }

  async function search(e?: SyntheticEvent<HTMLFormElement>) {
    e?.preventDefault();
    if (suggestions[active]) return choose(suggestions[active]);
    if (!text.trim()) return;
    setBusy(true);
    try {
      const [first] = await geocode(text, near, box, 1);
      if (first) choose(first);
      else setNotice(t.planner.noResults);
    } catch {
      setNotice(t.planner.searchDown);
    } finally {
      setBusy(false);
    }
  }

  function locate() {
    if (!navigator.geolocation) return setNotice(t.planner.noGeolocation);
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        setBusy(false);
        set('from', { lat: p.coords.latitude, lng: p.coords.longitude, label: t.planner.myLocation });
      },
      () => {
        setBusy(false);
        setNotice(t.planner.geolocationBlocked);
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

  const open = unfolded === searchKey;
  const sorted = result ? sortCandidates(result.candidates, sortBy) : [];
  // A drop-off picked on the map stays in the list.
  const rows = open ? sorted : sorted.filter((c, i) => i < ROWS_FOLDED || c.id === dropoff?.id);
  const folded = sorted.length - rows.length;
  const shared = sharedNames(result ? [result.pickup, ...result.candidates] : []);

  const captured = live.data ? new Date(live.data.captured_at) : null;
  const ageMin = captured ? (Date.now() - captured.getTime()) / 60_000 : null;
  const old = ageMin != null && ageMin > OLD_AFTER_MIN;
  const status = live.error
    ? t.apiProblem[live.error]
    : captured
      ? old
        ? t.planner.oldData(clock.format(captured), Math.round(ageMin!))
        : DEV
          ? t.planner.liveData(clock.format(captured))
          : ''
      : t.planner.loadingStations;

  const context = !start
    ? ''
    : !goal
      ? t.planner.askGoal
      : plan.error
        ? t.apiProblem[plan.error]
        : !result
          ? t.planner.computing
          : !dropoff
            ? t.planner.noDropoff
            : t.planner.summary(shortName(result.pickup.name), shortName(dropoff.name), pct(dropoff.p_free));

  const inset = {
    top: withDrawer ? PHONE_TRIP_BAR_PX : 0,
    bottom: withDrawer ? (showCard ? drawerPeek.px : 0) : docked ? DOCK_OVERLAP : 0,
    left: showCard && !phone ? CARD_WIDTH + 24 : 0,
    right: 0,
  };

  const optionsButton = (
    <button
      type="button"
      className={`ask__icon ${menu ? 'is-on' : ''}`}
      aria-label={t.planner.optionsButton}
      aria-expanded={menu}
      onClick={() => {
        // Close the phone keyboard, so the options stay in view.
        if (!menu && document.activeElement instanceof HTMLElement) document.activeElement.blur();
        setMenu((m) => !m);
      }}
    >
      <Sliders />
    </button>
  );

  // One row of the phone form. The row shows the picked place, and the typed text while it has the focus.
  const endField = (end: End) => {
    const picked = end === 'from' ? start : goal;
    return (
      <div className="trip-form__row">
        <span className="trip-form__icon" aria-hidden="true">
          {end === 'from' ? <span className="dot dot--start" /> : <Pin />}
        </span>
        <input
          ref={end === 'to' ? toInput : undefined}
          className="trip-form__input"
          type="text"
          enterKeyHint="search"
          value={editing === end && typing ? text : (picked?.label ?? '')}
          placeholder={end === 'from' ? t.planner.fromShort : t.planner.toShort}
          aria-label={end === 'from' ? t.planner.fromLabel : t.planner.toLabel}
          role="combobox"
          aria-expanded={editing === end && suggestions.length > 0}
          aria-controls="suggest"
          aria-autocomplete="list"
          autoComplete="off"
          onFocus={(e) => {
            setEditing(end);
            e.currentTarget.select();
          }}
          onChange={(e) => {
            setEditing(end);
            setText(e.target.value);
            setTyping(true);
            setMenu(false);
            setNotice('');
          }}
          onKeyDown={(e) => {
            // A form with two inputs and no submit button does not submit on Enter.
            if (e.key === 'Enter') {
              e.preventDefault();
              search();
            } else keys(e);
          }}
          onBlur={() => {
            setSuggestions([]);
            setTyping(false);
            setText('');
          }}
        />
        {end === 'from' && (
          <button type="button" className="trip-form__locate" aria-label={t.planner.myLocation} title={t.planner.myLocation} onClick={locate} disabled={busy}>
            <Locate />
          </button>
        )}
      </div>
    );
  };

  const menuBox = (
    <div
      className={`menu ${phone ? 'menu--sheet' : ''} ${menu ? 'is-open' : ''}`}
      role={phone ? 'dialog' : undefined}
      aria-label={phone ? t.planner.options : undefined}
      aria-hidden={!menu}
    >
      {phone && (
        <div className="menu__head">
          <strong>{t.planner.options}</strong>
          <button type="button" className="menu__close" aria-label={t.planner.closeOptions} onClick={() => setMenu(false)}>
            <Close />
          </button>
        </div>
      )}
      <div className="menu__row">
        <span className="menu__label">
          <Walk /> {t.planner.maxWalkLabel}
        </span>
        <div className="chips" role="radiogroup" aria-label={t.planner.maxWalk}>
          {RADII.map((r) => (
            <button key={r} type="button" role="radio" aria-checked={radius === r} className={`chip ${radius === r ? 'is-on' : ''}`} onClick={() => setRadius(r)}>
              {meters(r)}
            </button>
          ))}
        </div>
      </div>
      <div className="menu__row">
        <span className="menu__label">
          <Dock /> {t.planner.lostMinutesLabel}
        </span>
        <div className="chips" role="radiogroup" aria-label={t.planner.lostMinutes}>
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
        <span className="topbar__brand">
          <img className="topbar__logo" src="/yes_mex.png" alt="" /> ¡Sí hay!
        </span>
        <div className="topbar__end" ref={cornerRef}>
          {status && <span className={`topbar__status ${live.error ? 'is-error' : old ? 'is-old' : ''}`}>{status}</span>}
          <LangSwitch />
          <Help />
        </div>
      </header>

      <section
        className={`stage ${docked ? 'is-located' : ''}`}
        style={
          {
            '--card-width': `${CARD_WIDTH}px`,
            '--dock-height': `${dockSize.height}px`,
            '--corner-width': `${cornerSize.width}px`,
          } as CSSProperties
        }
      >
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
            onPickGoal={(p) => set('to', { ...p, label: t.planner.mapPoint })}
            lang={lang}
          />
        </div>
        {/* Without a start, the veil covers the map and blocks its clicks. */}
        <div className="stage__glass" aria-hidden="true" />

        {!docked && <h1 className="stage__title">{t.planner.title}</h1>}

        {withDrawer && (
          <button type="button" className="trip-reset" aria-label={t.planner.newSearch} title={t.planner.newSearch} onClick={resetTrip}>
            <Close />
          </button>
        )}
        {withDrawer && (
          <button
            type="button"
            className="trip-bar"
            aria-label={`${t.planner.editTrip}: ${goal!.label}`}
            onClick={() => {
              setMenu(false);
              setPlanning(true);
            }}
          >
            <span className="trip-form__icon" aria-hidden="true">
              <Pin />
            </span>
            <span className="trip-bar__text">{goal!.label}</span>
          </button>
        )}
        {phone && planning && start && goal && (
          <button type="button" className="stage__back" aria-label={t.planner.backToMap} onClick={() => setPlanning(false)}>
            <Close />
          </button>
        )}

        {showCard && (!phone || docked) && (
          <CardShell
            label={t.planner.whereToDrop}
            busy={plan.loading}
            drawer={
              withDrawer && {
                open: drawerOpen,
                onOpenChange: setDrawerOpen,
                // The loading rows are shorter than the station rows: wait for the plan.
                onPeekChange: (px) => result && setDrawerPeek((p) => (p.searchKey === searchKey ? p : { searchKey, px })),
                peekTo: '.card__list > li',
                openLabel: t.planner.openDrawer,
                closeLabel: t.planner.closeDrawer,
              }
            }
          >
            <div className="card__head">
              <div>
                <strong>{t.planner.whereToDrop}</strong>
                <span className="muted">
                  {result ? t.planner.stationsWithin(result.candidates.length, meters(result.radius_m)) : t.planner.computing}
                </span>
              </div>
              {!withDrawer && (
                <button type="button" className="icon-btn" aria-label={t.planner.close} onClick={() => setCardOpen(false)}>
                  <Close />
                </button>
              )}
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
                        {shortName(result.requested.name)} {whyNoBike(result.requested, t)}.
                      </span>
                    )}
                    {t.planner.takeBikeAt} <strong>{shortName(result.pickup.name)}</strong> <Code code={result.pickup.code} shown={shared.has(shortName(result.pickup.name))} />
                    <span className="facts muted">
                      {result.pickup.walk_m > 0 && (
                        <Fact icon={Walk} label={t.planner.walkToStation}>
                          {meters(result.pickup.walk_m)}
                        </Fact>
                      )}
                      <Fact icon={Bike} label={t.planner.bikesNow}>
                        {t.planner.bikes(String(result.pickup.bikes ?? '—'))}
                      </Fact>
                    </span>
                    {(result.pickup.p_empty_at_arrival ?? 0) >= EMPTY_RISK_SHOWN && (
                      <span className="muted">{t.planner.emptyRisk(pct(result.pickup.p_empty_at_arrival))}</span>
                    )}
                  </p>
                </div>
                <div className="sort" role="radiogroup" aria-label={t.planner.sortStations}>
                  {SORTS.map(({ key, icon: Icon }) => (
                    <button
                      key={key}
                      type="button"
                      role="radio"
                      aria-checked={sortBy === key}
                      aria-label={t.planner.sorts[key].hint}
                      title={t.planner.sorts[key].hint}
                      className={`sort__btn ${sortBy === key ? 'is-on' : ''}`}
                      onClick={() => setSortBy(key)}
                    >
                      <Icon />
                      <span>{t.planner.sorts[key].label}</span>
                    </button>
                  ))}
                </div>
                <ul className="card__list">
                  {rows.map((c) => (
                    <Row
                      key={c.id}
                      c={c}
                      selected={c.id === dropoff?.id}
                      withCode={shared.has(shortName(c.name))}
                      bike={c.id === dropoff?.id ? bikeText(legs) : ''}
                      onSelect={() => selectDropoff(c.id)}
                    />
                  ))}
                </ul>
                {(folded > 0 || open) && result.candidates.length > ROWS_FOLDED && (
                  <button type="button" className="card__more" aria-expanded={open} onClick={() => setUnfolded(open ? '' : searchKey)}>
                    <More />
                    {open ? t.planner.showLess : t.planner.showMore(folded)}
                  </button>
                )}
                <div className="card__legend">
                  <p className="card__legend-title">{t.planner.legendTitle}</p>
                  <div className="card__legend-items">
                    {FREE_LEGEND.map((l, i) => (
                      <span key={l}>
                        <i className={`swatch swatch--${i}`} aria-hidden="true" /> {l}
                      </span>
                    ))}
                  </div>
                </div>
                {shown && <RatePlan key={planId} shown={shown} />}
              </>
            )}
            {withDrawer && <TripCheck currentPlanId={planId} />}
          </CardShell>
        )}

        {phone && <div className={`menu__scrim ${menu ? 'is-open' : ''}`} aria-hidden="true" onClick={() => setMenu(false)} />}
        {/* The dock has a transform, so a fixed sheet inside it would stay on the dock. */}
        {phone && menuBox}
        <div className="dock" ref={dockRef}>
          {!phone && menuBox}
          {!(withDrawer && showCard) && <TripCheck currentPlanId={planId} />}
          {located && !phone && (
            <div className="dock__ends" role="group" aria-label={t.planner.trip}>
              <button type="button" className={`end ${editing === 'from' ? 'is-on' : ''}`} onClick={() => setEditing('from')}>
                <span className="dot dot--start" aria-hidden="true" />
                <span className="end__text">
                  <small>{t.planner.from}</small>
                  {start!.label}
                </span>
              </button>
              <button type="button" className={`end ${editing === 'to' ? 'is-on' : ''}`} onClick={() => setEditing('to')}>
                <span className="end__pin" aria-hidden="true">
                  <Pin />
                </span>
                <span className="end__text">
                  <small>{t.planner.to}</small>
                  {goal?.label ?? t.planner.pickGoal}
                </span>
              </button>
            </div>
          )}
          {/* On a phone, the form asks for the destination and the open card shows the best drop-off. */}
          {docked && context && !(phone && showCard) && (
            <div className="dock__context">
              <span>{context}</span>
              {start && goal && result && !cardOpen && (
                <button type="button" className="pill pill--sm" onClick={() => setCardOpen(true)}>
                  {t.planner.showStations}
                </button>
              )}
            </div>
          )}
          {/* With the drawer, the trip bar at the top replaces the form. */}
          <div className="ask-box" hidden={withDrawer}>
            {suggestions.length > 0 && (
              <ul className={`suggest ${docked ? '' : 'suggest--down'}`} role="listbox" id="suggest" aria-label={t.planner.suggestions}>
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
            {phone ? (
              <form className="trip-form" onSubmit={search} role="group" aria-label={t.planner.trip}>
                <div className="trip-form__ends">
                  {endField('from')}
                  {endField('to')}
                </div>
                {optionsButton}
              </form>
            ) : (
              <form className="ask" onSubmit={search}>
                {optionsButton}
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
                  aria-label={editing === 'from' ? t.planner.fromLabel : t.planner.toLabel}
                  placeholder={
                    editing === 'from'
                      ? located
                        ? t.planner.changeStart
                        : t.planner.askStart
                      : t.planner.askGoalShort
                  }
                />
                {editing === 'from' && (
                  <button type="button" className="ask__locate" onClick={locate} disabled={busy}>
                    <Locate />
                    <span>{t.planner.myLocation}</span>
                  </button>
                )}
                <button type="submit" className="ask__send" aria-label={t.planner.search} disabled={busy || !text.trim()}>
                  <Send />
                </button>
              </form>
            )}
          </div>
          {notice && <p className="stage__hint">{notice}</p>}
        </div>
      </section>
    </>
  );
}
