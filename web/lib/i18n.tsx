'use client';

// Interface texts in Spanish (default) and English. The choice stays in this browser. Station names, street names and
// Photon answers stay in their source language.

import { type ReactNode, useSyncExternalStore } from 'react';

export type Lang = 'es' | 'en';
export const LANGS: Lang[] = ['es', 'en'];
const DEFAULT_LANG: Lang = 'es';
const LANG_KEY = 'ecobici-lang-v1';

export type ApiProblem = 'no_live_data' | 'no_bike_near_start' | 'bad_request' | 'api_down';
type StationState = 'available' | 'full' | 'unavailable' | 'stale';

const es = {
  locale: 'es-MX',
  langName: 'Español',
  langSwitch: 'Idioma',
  apiProblem: {
    no_live_data: 'Todavía no hay datos en vivo. Intenta en un minuto.',
    no_bike_near_start: 'No hay estaciones con bicis cerca del punto de partida.',
    bad_request: 'No se pudo calcular el viaje con esos datos.',
    api_down: 'El servicio de predicción no responde. ¿Está corriendo la API?',
  } satisfies Record<ApiProblem, string>,
  stationState: {
    available: 'Disponible',
    full: 'Llena',
    unavailable: 'Fuera de servicio',
    stale: 'Sin datos recientes',
  } satisfies Record<StationState, string>,
  whyNoBike: {
    unavailable: 'está fuera de servicio',
    stale: 'no envía datos recientes',
    empty: 'no tiene bicis ahora',
  },
  places: {
    station: (code: string) => `Estación Ecobici ${code}`,
    kinds: {} as Record<string, string>,
  },
  planner: {
    sorts: {
      time: { label: 'Tiempo', hint: 'Ordenar por tiempo de viaje' },
      walk: { label: 'Caminar', hint: 'Ordenar por distancia a pie al destino' },
      free: { label: 'Disponibilidad', hint: 'Ordenar por probabilidad de lugar libre' },
    },
    best: 'Mejor',
    arriveAtGoal: 'Llegas a tu destino',
    walkToGoal: 'A pie hasta tu destino',
    docksNow: 'Lugares libres ahora',
    docksFree: (n: string) => `${n} libres`,
    byBike: 'En bici',
    searchDown: 'La búsqueda de direcciones no responde. Los lugares conocidos sí funcionan.',
    noResults: 'No hay resultados en la zona de Ecobici. Agrega la colonia.',
    noGeolocation: 'Este navegador no comparte la ubicación.',
    geolocationBlocked: 'La ubicación está bloqueada o no está disponible. Escribe una dirección.',
    myLocation: 'Mi ubicación',
    mapPoint: 'Punto en el mapa',
    oldData: (time: string, min: number) => `Sin datos recientes · última lectura a las ${time} (hace ${min} min)`,
    liveData: (time: string) => `En vivo · estaciones leídas a las ${time}`,
    loadingStations: 'Cargando estaciones…',
    askGoal: 'Ahora, ¿a dónde vas? Escríbelo o haz doble clic en el mapa.',
    computing: 'Calculando…',
    noDropoff: 'Ahora no se puede recomendar ninguna estación cerca del destino.',
    summary: (pickup: string, dropoff: string, chance: string) =>
      `Toma la bici en ${pickup} y déjala en ${dropoff}: ${chance} de encontrar lugar`,
    options: 'Opciones',
    closeOptions: 'Cerrar opciones',
    maxWalkLabel: 'Máximo a pie hasta tu destino',
    maxWalk: 'Máximo a pie',
    lostMinutesLabel: 'Minutos perdidos si la estación está llena',
    lostMinutes: 'Minutos perdidos',
    title: '¿A dónde vas en bici?',
    whereToDrop: 'Dónde dejar la bici',
    stationsWithin: (n: number, distance: string) => `${n} estaciones a ${distance} o menos de tu destino`,
    close: 'Cerrar',
    takeBikeAt: 'Toma la bici en',
    walkToStation: 'A pie hasta la estación',
    bikesNow: 'Bicis ahora',
    bikes: (n: string) => `${n} bicis`,
    emptyRisk: (chance: string) => `${chance} de que se acaben antes de que llegues`,
    sortStations: 'Ordenar estaciones',
    showLess: 'Ver menos',
    showMore: (n: number) => `Ver ${n} más`,
    legendTitle: 'Probabilidad de lugar libre al llegar',
    lanesTitle: 'Ciclovías',
    lanes: { separated: 'Separada', painted: 'Pintada', shared: 'Compartida' },
    trip: 'Viaje',
    from: 'Desde',
    to: 'Hasta',
    pickGoal: 'Elige un destino',
    showStations: 'Ver estaciones',
    suggestions: 'Sugerencias',
    optionsButton: 'Opciones: distancia a pie y minutos perdidos',
    fromLabel: 'Desde dónde sales',
    toLabel: 'A dónde vas',
    changeStart: 'Cambia el punto de partida: calle, lugar o estación',
    askStart: '¿Desde dónde sales? Calle, lugar o estación',
    askGoalShort: '¿A dónde vas? Calle, lugar o estación',
    fromShort: '¿Desde dónde sales?',
    toShort: '¿A dónde vas?',
    editTrip: 'Cambiar inicio o destino',
    backToMap: 'Volver al mapa',
    newSearch: 'Nueva búsqueda: borra el inicio y el destino',
    openDrawer: 'Ver todas las estaciones',
    closeDrawer: 'Ver el mapa',
    search: 'Buscar',
  },
  map: {
    routesCredit: 'Rutas: OSRM, FOSSGIS',
    docksOf: (docks: string, capacity: string, bikes: string) => `${docks} lugares libres de ${capacity} · ${bikes} bicis`,
    freeOnArrival: 'Lugar libre al llegar',
    fullIn: 'Llena en 15 / 30 / 45 min',
    noForecast: 'Sin pronóstico',
    emptyIn15: 'Sin bicis en 15 min',
    broken: 'Tu navegador no puede mostrar el mapa. El plan sigue funcionando.',
    label: 'Mapa. Haz doble clic para elegir el destino.',
  },
  feedback: {
    privacy: 'Anónimo. Guardamos solo las estaciones y tu respuesta para mejorar el modelo.',
    reasons: { far: 'Me deja lejos', wrong_time: 'El tiempo no cuadra', wrong_data: 'Datos incorrectos', other: 'Otra razón' },
    thanks: 'Gracias.',
    useful: '¿Te sirvió esta recomendación?',
    yes: 'Sí',
    no: 'No',
    whyNot: '¿Por qué no?',
    whatFailed: 'Qué falló',
    whatFailedHint: '¿Qué falló? Sin datos personales, por favor.',
    send: 'Enviar',
    sendFailed: 'No se pudo enviar. Intenta de nuevo.',
    lastTrip: 'Tu último viaje',
    dontAsk: 'No preguntar',
    tripThanks: 'Gracias. Tu respuesta nos ayuda a mejorar las predicciones.',
    foundDock: (dropoff: ReactNode) => <>¿Encontraste lugar para dejar la bici en {dropoff}?</>,
    noTrip: 'No hice el viaje',
    foundBike: (pickup: ReactNode) => <>¿Había bici en {pickup} cuando llegaste?</>,
  },
  help: {
    open: 'Cómo usar la app',
    close: 'Cerrar',
    steps: [
      {
        title: 'Elige desde dónde sales',
        art: 'Mapa con tu punto de partida',
        text: (
          <>
            Escribe una calle, un lugar o una estación, o toca <em>Mi ubicación</em>.
          </>
        ),
      },
      { title: 'Elige a dónde vas', art: 'Ruta hasta tu destino', text: <>Escríbelo o haz doble clic en el mapa.</> },
      {
        title: 'Sigue la recomendación',
        art: 'Bici y estación recomendada',
        text: (
          <>
            Te decimos dónde tomar la bici y en qué estación dejarla. La <strong>#1</strong> es la mejor; toca otra para ver
            su ruta.
          </>
        ),
      },
      {
        title: 'Qué significa el porcentaje',
        art: 'Probabilidad de lugar libre',
        text: (
          <>
            La probabilidad de encontrar lugar libre <strong>a la hora en que llegas</strong>.
          </>
        ),
      },
    ],
    stepsLabel: 'Pasos',
    step: (n: number, title: string) => `Paso ${n}: ${title}`,
    dontShow: 'No volver a mostrar',
    back: 'Atrás',
    next: 'Siguiente',
    start: 'Empezar',
  },
};

export type Messages = typeof es;

const en: Messages = {
  locale: 'en-GB',
  langName: 'English',
  langSwitch: 'Language',
  apiProblem: {
    no_live_data: 'No live data yet. Try again in a minute.',
    no_bike_near_start: 'No station with bikes near the start.',
    bad_request: 'The trip cannot be calculated with this data.',
    api_down: 'The prediction service does not respond. Is the API running?',
  },
  stationState: { available: 'Available', full: 'Full', unavailable: 'Out of service', stale: 'No recent data' },
  whyNoBike: { unavailable: 'is out of service', stale: 'sends no recent data', empty: 'has no bikes now' },
  places: {
    station: (code) => `Ecobici station ${code}`,
    kinds: {
      Alcaldía: 'Borough',
      Colonia: 'Neighbourhood',
      Metro: 'Metro',
      Metrobús: 'Metrobús',
      'Tren ligero': 'Light rail',
      Estación: 'Station',
      Museo: 'Museum',
      'Lugar turístico': 'Tourist attraction',
      Monumento: 'Monument',
      Parque: 'Park',
      'Plaza comercial': 'Shopping centre',
      Universidad: 'University',
      Hospital: 'Hospital',
      Teatro: 'Theatre',
      Biblioteca: 'Library',
      Edificio: 'Building',
    },
  },
  planner: {
    sorts: {
      time: { label: 'Time', hint: 'Sort by trip time' },
      walk: { label: 'Walk', hint: 'Sort by walking distance to the destination' },
      free: { label: 'Availability', hint: 'Sort by chance of a free dock' },
    },
    best: 'Best',
    arriveAtGoal: 'You arrive at your destination',
    walkToGoal: 'Walk to your destination',
    docksNow: 'Free docks now',
    docksFree: (n) => `${n} free`,
    byBike: 'By bike',
    searchDown: 'The address search does not respond. Known places still work.',
    noResults: 'No results in the Ecobici area. Add the neighbourhood.',
    noGeolocation: 'This browser does not share your location.',
    geolocationBlocked: 'Location is blocked or not available. Type an address.',
    myLocation: 'My location',
    mapPoint: 'Point on the map',
    oldData: (time, min) => `No recent data · last reading at ${time} (${min} min ago)`,
    liveData: (time) => `Live · stations read at ${time}`,
    loadingStations: 'Loading stations…',
    askGoal: 'Now, where are you going? Type it or double-click the map.',
    computing: 'Calculating…',
    noDropoff: 'No station near the destination can be recommended now.',
    summary: (pickup, dropoff, chance) => `Take the bike at ${pickup} and leave it at ${dropoff}: ${chance} chance of a free dock`,
    options: 'Options',
    closeOptions: 'Close options',
    maxWalkLabel: 'Maximum walk to your destination',
    maxWalk: 'Maximum walk',
    lostMinutesLabel: 'Minutes lost if the station is full',
    lostMinutes: 'Minutes lost',
    title: 'Where are you riding to?',
    whereToDrop: 'Where to leave the bike',
    stationsWithin: (n, distance) => `${n} stations within ${distance} of your destination`,
    close: 'Close',
    takeBikeAt: 'Take the bike at',
    walkToStation: 'Walk to the station',
    bikesNow: 'Bikes now',
    bikes: (n) => `${n} bikes`,
    emptyRisk: (chance) => `${chance} chance they run out before you arrive`,
    sortStations: 'Sort stations',
    showLess: 'Show less',
    showMore: (n) => `Show ${n} more`,
    legendTitle: 'Chance of a free dock on arrival',
    lanesTitle: 'Bike lanes',
    lanes: { separated: 'Separated', painted: 'Painted', shared: 'Shared' },
    trip: 'Trip',
    from: 'From',
    to: 'To',
    pickGoal: 'Choose a destination',
    showStations: 'Show stations',
    suggestions: 'Suggestions',
    optionsButton: 'Options: walking distance and minutes lost',
    fromLabel: 'Where you start',
    toLabel: 'Where you are going',
    changeStart: 'Change the start: street, place or station',
    askStart: 'Where do you start? Street, place or station',
    askGoalShort: 'Where are you going? Street, place or station',
    fromShort: 'Where do you start?',
    toShort: 'Where are you going?',
    editTrip: 'Change the start or the destination',
    backToMap: 'Back to the map',
    newSearch: 'New search: clear the start and the destination',
    openDrawer: 'Show all the stations',
    closeDrawer: 'Show the map',
    search: 'Search',
  },
  map: {
    routesCredit: 'Routes: OSRM, FOSSGIS',
    docksOf: (docks, capacity, bikes) => `${docks} free docks of ${capacity} · ${bikes} bikes`,
    freeOnArrival: 'Free dock on arrival',
    fullIn: 'Full in 15 / 30 / 45 min',
    noForecast: 'No forecast',
    emptyIn15: 'No bikes in 15 min',
    broken: 'Your browser cannot show the map. The plan still works.',
    label: 'Map. Double-click to choose the destination.',
  },
  feedback: {
    privacy: 'Anonymous. We keep only the stations and your answer, to improve the model.',
    reasons: { far: 'Too far from my destination', wrong_time: 'The time is wrong', wrong_data: 'Wrong data', other: 'Other reason' },
    thanks: 'Thank you.',
    useful: 'Was this recommendation useful?',
    yes: 'Yes',
    no: 'No',
    whyNot: 'Why not?',
    whatFailed: 'What went wrong',
    whatFailedHint: 'What went wrong? No personal data, please.',
    send: 'Send',
    sendFailed: 'Could not send. Try again.',
    lastTrip: 'Your last trip',
    dontAsk: 'Do not ask',
    tripThanks: 'Thank you. Your answer helps us improve the predictions.',
    foundDock: (dropoff) => <>Did you find a free dock at {dropoff}?</>,
    noTrip: 'I did not make the trip',
    foundBike: (pickup) => <>Was there a bike at {pickup} when you arrived?</>,
  },
  help: {
    open: 'How to use the app',
    close: 'Close',
    steps: [
      {
        title: 'Choose where you start',
        art: 'Map with your start point',
        text: (
          <>
            Type a street, a place or a station, or tap <em>My location</em>.
          </>
        ),
      },
      { title: 'Choose where you are going', art: 'Route to your destination', text: <>Type it or double-click the map.</> },
      {
        title: 'Follow the recommendation',
        art: 'Bike and recommended station',
        text: (
          <>
            We tell you where to take the bike and at which station to leave it. <strong>#1</strong> is the best; tap another
            one to see its route.
          </>
        ),
      },
      {
        title: 'What the percentage means',
        art: 'Chance of a free dock',
        text: (
          <>
            The chance of a free dock <strong>at the time you arrive</strong>.
          </>
        ),
      },
    ],
    stepsLabel: 'Steps',
    step: (n, title) => `Step ${n}: ${title}`,
    dontShow: 'Do not show again',
    back: 'Back',
    next: 'Next',
    start: 'Start',
  },
};

export const MESSAGES: Record<Lang, Messages> = { es, en };

const listeners = new Set<() => void>();
let memoryLang: Lang | null = null;

function readLang(): Lang {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    return LANGS.includes(saved as Lang) ? (saved as Lang) : DEFAULT_LANG;
  } catch {
    return DEFAULT_LANG;
  }
}

export function setLang(lang: Lang) {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch {
    // No localStorage (private mode): the choice lasts until the page closes.
    memoryLang = lang;
  }
  for (const notify of listeners) notify();
}

function subscribe(notify: () => void) {
  listeners.add(notify);
  return () => listeners.delete(notify);
}

/** The interface language. The static HTML is in Spanish, so the server snapshot is the default. */
export function useLang(): Lang {
  return useSyncExternalStore(subscribe, () => memoryLang ?? readLang(), () => DEFAULT_LANG);
}

export function useMessages(): Messages {
  return MESSAGES[useLang()];
}
