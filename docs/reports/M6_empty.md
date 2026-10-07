# M6-empty: probabilidad de que no haya bici para tomar

Fecha: 2026-10-07. Reproducible con `uv run python -m ecobici.eval.model_report --target empty --horizons 15` (~7.5 min, 1 horizonte). Artefactos en `artifacts/empty/`.

## Por qué

El modelo M6 predice si la estación de **llegada** tendrá anclaje libre. Para la estación donde se **toma** la bici hace falta lo contrario: si todavía tendrá una bici cuando la persona llegue caminando. En el planificador, la estación de partida podía quedarse sin bicis. En CE-563 Doctor Velasco - Niños Héroes, por ejemplo, la app decía "toma una bici aquí · 0 bicis ahora".

Estar vacía es mucho más común que estar llena: en octubre de 2025, el 30 % de las lecturas no tenía bicis y solo el 2.5 % no tenía anclajes.

## Qué cambia respecto a M6

Todo es igual (datos, variables, líneas base, validación, bootstrap), salvo el estado que se predice. `targets.load_snapshots(target="empty")` define:

- **Objetivo:** `num_bikes_available = 0` (las bicis deshabilitadas ya no cuentan).
- **En servicio:** `is_installed`, sin `is_renting`. En MaxHalford, `is_renting` es falso en casi todas las lecturas sin bicis (379 mil de 379 mil en 2025-10): marca "sin bicis", no una falla. Filtrar con él quitaría justo los casos a predecir. En el feed en vivo de hoy sí se usa distinto (133 estaciones vacías dicen "renting"), así que tampoco es estable.

Con ese cambio, todas las piezas "de llena" pasan a ser "de vacía": la persistencia, la persistencia calibrada, los rezagos (`full_lag15` = vacía hace 15 min), las vecinas (`nb_full_frac` = fracción de vecinas vacías) y el perfil de la estación. Los nombres de las variables no cambian porque están dentro del booster congelado de M6. El corte "saturadas" pasa a ser **estaciones que se vacían** en el pico: 460 estaciones con ≥ 10 % de lecturas vacías entre semana de 08:30 a 10:30 en TRAIN.

Solo 15 min: la caminata a la estación de partida dura minutos, y MaxHalford (lecturas cada ~15 min) no permite horizontes más cortos.

## Resultados (VAL_REPORT, 2025-10 → 2025-12, 15 min)

| Corte | Tasa de vacía | Mejor línea base | Brier línea base | Brier modelo | BSS | IC 95 % (días) |
| --- | --- | --- | --- | --- | --- | --- |
| Todas | 0.311 | promedio histórico | 0.0706 | 0.0388 | **+0.451** | [+0.432, +0.473] |
| Pico | 0.189 | persistencia calibrada | 0.1140 | 0.0892 | **+0.218** | [+0.207, +0.226] |
| Se vacían | 0.314 | promedio histórico | 0.0729 | 0.0416 | **+0.430** | [+0.408, +0.453] |
| Se vacían + pico | 0.255 | persistencia calibrada | 0.1492 | 0.1162 | **+0.221** | [+0.212, +0.228] |

Modelo: `p_lgbm_sub_roll`, la misma receta que el modelo congelado de M6 (isotónica global y Platt semanal en el subgrupo).

- **Calibración en "se vacían + pico":** brecha de 0.016, IC [0.011, 0.029]. Cumple con holgura. Todos los bins están a ≤ 0.016 de la diagonal ([figura](figures/M6_reliability_empty.png)). Con diez veces más casos positivos que "llena", la calibración es mucho más estable.
- **La persistencia simple es mala** (BSS −0.13 en todas): una estación vacía ahora a menudo recibe bicis en 15 min.
- **Lo que más pesa:** `bikes_now` (63 %), las salidas históricas de viajes en la franja de llegada (14 %) y la hora (9 %). Los viajes de M4 aportan mucho más aquí que en el modelo de llena.
- V8 sin brechas: ECE ≤ 0.0025 en centro y periferia.

## Lo que falta

- **Sin prueba final fuera de muestra:** los meses de prueba (2026-01, 2026-09) ya se usaron en M6. Este modelo se confirma en la captura propia (paso 9), con el mismo bootstrap por días.
- **Horizonte corto:** el planificador escala la probabilidad linealmente con la caminata, de 0 (hay bici ahora) a P(15 min). Es una aproximación hasta tener modelos a 5 y 10 min con la captura a 2 min (M7).

## Cómo se usa en el planificador

`recommender.plan.pickup_options` toma hasta 4 estaciones con bici a ≤ 600 m a pie del punto de partida. Para cada una, `serve.LiveService.plan` calcula el destino óptimo y suma:

caminata + P(sin bici al llegar) × costo de falla + bici + caminata + P(llena al llegar) × costo de falla

y elige la de menor total. Si la estación de partida elegida no tiene bicis ahora, la API lo dice (`requested`) y ofrece la mejor cercana.

Además, el destino ahora lee P(llena) a la llegada real: caminata a la estación de partida + viaje. Antes leía solo el tiempo del viaje.
