# M3 — ¿Se llenan las estaciones? (V1) ¿Fallan juntas? (V6)

Fecha: 2026-10-06. Datos: los 16 meses sanos de MaxHalford (2024-09 → 2026-01, menos 2025-07), 28.6 M lecturas. Reproducible con `uv run python -m ecobici.eval.saturation`.

"Llena" = instalada, aceptando devoluciones y 0 anclajes libres. Las lecturas fuera de servicio se excluyen. "Vecina" = a ≤ 500 m a pie (haversine × 1.3).

## V1 — saturation
- Overall full rate: 2.7%
- Weekday full rate by hour: 0h 5.4%, 1h 5.2%, 2h 4.4%, 3h 3.6%, 4h 3.1%, 5h 2.4%, 6h 1.2%, 7h 0.8%, 8h 2.1%, 9h 4.6%, 10h 4.2%, 11h 3.1%, 12h 2.3%, 13h 1.9%, 14h 1.5%, 15h 1.4%, 16h 1.3%, 17h 1.1%, 18h 1.3%, 19h 1.9%, 20h 2.5%, 21h 2.9%, 22h 4.1%, 23h 5.4%
- Weekday 08:30–10:30: of 678 stations, 99 are full >=10% of the time, 36 >=25%, 0 >=50%
- Most saturated at 08:30–10:30:
  - CE-025 Reforma - Estocolmo (capacity 27): 48.1%
  - CE-455 Pedregal-Ferrocarril De Cuernavaca (capacity 23): 42.8%
  - CE-240 Ejército Nacional-F.C. de Cuernavaca (capacity 17): 40.5%
  - CE-459 Volcán-Montes Urales (capacity 31): 40.4%
  - CE-239 Rincón del Bosque-Ruben Darío (capacity 19): 38.5%
  - CE-303 Montecito-Av. Insurgentes (capacity 26): 37.5%
  - CE-246 Leibnitz-Thiers (capacity 15): 37.4%
  - CE-226 Wallon-Presidente Masaryk (capacity 27): 37.2%
  - CE-015 Reforma - Río Mississippi (capacity 23): 37.0%
  - CE-206 Homero-Moliere (capacity 23): 36.6%
  - CE-241 Ejército Nacional-Juan Vázquez de la Mella (capacity 19): 36.4%
  - CE-250 Darwin-Mariano Escobedo (capacity 23): 36.2%
  - CE-197 Presa Falcón - Miguel De Cervantes Saavedra (capacity 31): 36.0%
  - CE-227 Campos Elíseos-Periférico (capacity 23): 35.8%
  - CE-209 Solón-Horacio (capacity 19): 35.8%

## V6 — neighbours fail together
- Stations with a walkable neighbour: 669 of 692 (mean 4.1 neighbours)
- Base full rate: 2.7%
- P(B full | A full): 22.7% (<200 m: 29.1%, >=200 m: 21.2%)
- When A is full: P(any neighbour full) 48.7%, P(all neighbours full) 7.8% over 743,206 full readings

## Conclusiones

**V1: la saturación es real, pero concentrada.**
- En promedio, una estación está llena solo el 2.7 % del tiempo. Una métrica global quedaría dominada por estaciones que casi nunca se llenan.
- Entre semana, de 08:30 a 10:30 (la llegada al trabajo), **36 estaciones están llenas ≥ 25 % del tiempo y 99 al menos ≥ 10 %**. Las más saturadas están en Polanco, Reforma, Nuevo Polanco y Lomas, zonas de oficinas. Coincide con la hipótesis del PRD.
- Ninguna supera el 50 %. Ni la peor estación está llena la mayor parte del tiempo, así que una regla fija ("evita la estación X") no alcanza. Hace falta predecir cuándo.
- Hay un segundo pico de noche (22–01 h, ~5 %). Es otro fenómeno, probablemente devoluciones al cierre o el rebalanceo, y queda fuera del caso de uso de la llegada al trabajo.

**V6: las vecinas sí fallan juntas, pero casi siempre hay respaldo.**
- P(B llena | A llena) = **22.7 %**, unas 8 veces la tasa base (2.7 %). Sube a 29 % cuando B está a menos de 200 m. El riesgo de "fallas correlacionadas" del PRD es real, y elegir el respaldo por baja dependencia (RF6) está justificado.
- Aun así, cuando A está llena, **todas sus vecinas lo están solo el 7.8 % del tiempo**. En el ~92 % de los casos existe un respaldo útil. La mitad de las veces (48.7 %) al menos una vecina también está llena, así que importa elegir bien cuál.

## Limitaciones

- Es una tasa **por tiempo**, no **por llegada**. Las llegadas se concentran en el pico, así que lo que vive un usuario es probablemente peor que estos números. La versión por llegada necesita los viajes (M4).
- Con lecturas cada ~15 min, episodios cortos de "llena" pueden no aparecer.

## Recomendación

**GO.** El problema existe y está concentrado donde el PRD lo esperaba. Propuesta de criterio V1, que el PRD dejaba "por definir": al menos 25 estaciones llenas ≥ 25 % del tiempo en el pico de la mañana. Se cumple con 36.

Implicación para M5–M8: además de las métricas globales, reportar Brier, BSS y calibración **en el subconjunto de ~100 estaciones saturadas en el pico**, y evaluar V9 con viajes que terminan en esas zonas.
