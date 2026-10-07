# Siguientes pasos: del modelo M6 a la prueba final

Estado al 2026-10-07, actualizado tras la prueba final (paso 8). Resume la revisión de [`modeling.md`](modeling.md) y lo que se decidió después de revisar la captura propia. Los plazos y las etapas generales siguen en [`ENG_PLAN.md`](ENG_PLAN.md).

## Dónde estamos

- **M6, precisión:** en VAL_REPORT (2025-10 → 2025-12), LightGBM reduce el Brier ~20 % frente a la mejor línea base en todos los cortes y horizontes (BSS +0.17 … +0.22).
  - **Es del modelo:** con líneas base que ven los mismos datos (TRAIN + VAL_FIT), el BSS baja como mucho 0.002.
  - **No es ruido:** en saturadas + pico, el IC 95 % por días es [+0.20, +0.23] a 15 min, [+0.20, +0.24] a 30 min y [+0.18, +0.23] a 45 min.
  - El log loss baja ~35 %.
- **M6, calibración en saturadas + pico:** con la calibración por subgrupo (paso 3) cumple la meta (≤ 0.05) en los tres horizontes, justo en el límite del IC.
  - `p_lgbm` (fijado de antemano): 0.059 [0.044, 0.085] / 0.047 [0.039, 0.076] / 0.073 [0.054, 0.107] a 15 / 30 / 45 min.
  - **`p_lgbm_sub_roll` (congelado):** 0.028 [0.018, 0.050] / 0.029 [0.021, 0.049] / 0.032 [0.025, 0.051], y el BSS sube 0.003–0.008.
  - Se eligió después de ver VAL_REPORT, así que la prueba final decide. Detalle en [M6](reports/M6_lgbm.md#calibración-por-subgrupo-2026-10-06).
- **Captura propia:** corre desde el 2026-10-06. El primer día solo tiene ~3 h continuas (11:37–14:38 hora local), sin pico de la mañana. Todavía no sirve para medir el modelo.
- **Prueba final (paso 8, 2026-10-07): cumple en 2026-01 y 2026-09.** Detalle en [M6_test](reports/M6_test.md).
  - **Precisión confirmada:** BSS en saturadas + pico de +0.238 / +0.229 / +0.217 (2026-01) y +0.247 / +0.253 / +0.247 (2026-09). El límite inferior más bajo en cualquier corte es +0.155.
  - **Calibración: cumple en el valor puntual, sin holgura.** Con un mes, pocos bins llegan a 1,000 filas. Mirando todos, en 2026-01 el modelo congelado subestima 3–7 puntos en el rango medio a 30 y 45 min: el Platt semanal se ajustó con diciembre y corrigió de más.
  - **La calibración por subgrupo no aportó en la prueba** (BSS 0.001–0.003 por debajo de `p_lgbm`). Se decide en la captura propia (paso 9).
  - Los meses de prueba ya están usados: no sirven para elegir ni ajustar nada más.

## Qué significa un horizonte

El horizonte es cuánto tiempo hacia adelante predice el modelo: del momento en que la persona sale al momento en que llega a la estación. En la práctica equivale a la duración del viaje. Hay un modelo por horizonte porque predecir a 45 min es más difícil que a 15. Un viaje que cae entre dos horizontes usa el más cercano o una mezcla de los dos. El viaje típico dura 12–14 min, así que 10, 15 y 20 min son los horizontes más importantes.

## Decisión: estaciones `stale` (2026-10-06)

- **La captura no pierde datos.** El colector guarda los bytes crudos del feed. La captura coincide con el feed en vivo (mismas 677 estaciones, mismo `last_reported` en las estaciones sin reportar).
- **El campo `last_reported` se queda.** El modelo no lo usa, porque MaxHalford no lo tiene. Sirve como control de calidad para las etiquetas y para el recomendador.
- **Umbral de `stale`: 3 h** (antes 30 min, provisional). Las estaciones reportan solo cuando cambian. Con 30 min, de las 24 estaciones en servicio marcadas `stale`, 17 llevaban 30–60 min sin reportar y 12 no tenían bicis, es decir, todos los anclajes libres: estaciones tranquilas, no rotas. Con 3 h, las lecturas `stale` bajan de 9.6 % a 0.22 %.
- **El recomendador no propone estaciones `stale` ni fuera de servicio** (`labels.is_recommendable`).
- **Pendiente:** fijar el umbral final con una semana de captura. `ecobici-capture-report` muestra cuánto tiempo pasan sin reportar las estaciones en servicio, incluidas noches y fines de semana.

## Pasos

### Esta semana, sin tocar los datos de prueba

1. ✅ **Mismas condiciones para líneas base y modelo** (2026-10-06).
   - `p_persist_cal` y `p_hist` se reajustaron con TRAIN + VAL_FIT (`_tvf`), y también se recalibraron con isotónica en VAL_FIT (`_iso`).
   - La "referencia justa" es la mejor de todas. El BSS baja ≤ 0.002, así que casi todo el ~20 % es del modelo.
   - Ver [M6](reports/M6_lgbm.md#comparación-justa-e-intervalos-de-confianza-2026-10-06).
2. ✅ **Intervalos de confianza** (2026-10-06).
   - Bootstrap por bloques (`ecobici.eval.bootstrap`, 1,000 réplicas), por día y por estación × día.
   - Los bloques por día dan IC ~2× más anchos y son los de referencia: hay correlación entre estaciones dentro de un mismo día.
   - El reporte agrega log loss y el diagrama de confiabilidad (`docs/reports/figures/M6_reliability.png`).
3. ✅ **Calibración por subgrupo (saturadas + pico)** (2026-10-06).
   - Platt sobre `p_lgbm`, solo en el subgrupo, reajustado cada semana con los 28 días anteriores. Si la ventana tiene < 5,000 filas, usa el Platt fijo ajustado en VAL_FIT (`p_lgbm_sub`).
   - **Criterio de éxito: cumplido en el límite.** Brecha 0.028 / 0.029 / 0.032 y extremo superior del IC por días de 0.050 / 0.049 / 0.051. El BSS sube.
   - El sesgo tenía una parte del subgrupo (~2 puntos ya en VAL_FIT) y otra de temporada (4–6 puntos en VAL_REPORT). Por eso el Platt fijo solo no basta: su IC llega a 0.059 / 0.058 / 0.072.
   - **Congelado:** `p_lgbm_sub_roll` (`FROZEN` en `model_report.py`). `p_lgbm` sigue como el modelo fijado de antemano. TEST no se miró.
4. ✅ **Septiembre de 2026** (2026-10-06). Solo se miraron marcas de tiempo; detalle en [M2](reports/M2_history.md#2026-09-en-detalle-2026-10-06).
   - Los 72 huecos están todos del 1 al 10, la cola del scraper degradado. **Desde el 11 a las 04:13 el feed es continuo.**
   - **Decisión:** 2026-09 cuenta desde el 11 (`splits.TEST_FROM`). Del 1 al 10 se excluye. No hace falta filtrar huecos sueltos: el filtro por ejemplo ya lo hace.
   - **Ojo:** desde el 11 la cadencia es de 12 min fijos, no ~15.5. Las etiquetas a 15 / 30 / 45 min se leen a 12 / 24 / 48 min, y `docks_lag15` falta casi siempre. El Brier absoluto no se compara con 2026-01, solo el BSS.
   - **2026-01 es la prueba principal.** 2026-09 (~14 días hábiles, en temporada de lluvias) se reporta aparte.
5. **Pipeline de evaluación sobre la captura.** GBFS JSON → las mismas 33 variables → predicciones → métricas. Probarlo solo en la ventana del 2026-10-06, 11:37–14:38 hora local (17:37–20:38 UTC). Esa ventana queda marcada como *dev* y fuera de la prueba final para siempre.

### Hecho después de la prueba final (2026-10-07)

- **Predicciones en vivo y API** (primer corte del paso 5): `ecobici.live` lleva la captura propia por el mismo código de variables. `ecobici.api` (FastAPI) sirve `/v1/stations` y `/v1/plan` leyendo S3 con la sesión de `aws login` (`botocore[crt]`), sin llaves.
- **Planificador web** (`web/`, Next 16, sobre el esqueleto de *a-donde-ir*): dirección o estación de partida y de destino, estaciones a ≤ 500 m del destino con P(anclaje libre) a su propia hora de llegada (PRD RF1–RF5, RF7, RF9).
- **Modelo de estación vacía** (P(sin bici) a 15 min): BSS +0.45 en todas y +0.22 en el pico, calibración con holgura. La estación de partida se elige con él ([M6-empty](reports/M6_empty.md)). Falta confirmarlo en la captura (paso 9).
- **Pendiente del planificador:** respaldo con baja dependencia de la principal (RF6), y P(sin bici) a 5 y 10 min con la captura (M7).

### Probado y descartado

- **Rezagos con ventana centrada** (2026-10-07). Recupera casi todos los rezagos (de ~47 % a ~95 %), pero en VAL_REPORT el BSS cambia ≤ 0.003 y la calibración no cambia. El modelo congelado sigue con `trailing`. Ver [M6](reports/M6_lgbm.md#experimento-rezagos-con-ventana-centrada-2026-10-07).

### Mientras corre la captura (2–4 semanas)

6. **Revisar la salud de la captura cada pocos días** (ver [Cómo sincronizar](#cómo-sincronizar-la-captura)). Un hueco como el del primer día (105 min) no debe repetirse en las mañanas entre semana.
7. *(Opcional)* Agregar `botocore[crt]` al extra `collector`, desde PyPI, para no tener que exportar credenciales.

### Después, una sola vez

8. ✅ **Prueba final de 15, 30 y 45 min** (2026-10-07). Protocolo registrado y commit antes de correr (`4b2c0eb`), corrida única con `ecobici.eval.test_report`. **Cumple los tres criterios en los dos meses.** Ver [M6_test](reports/M6_test.md).
9. **Prueba en datos reales:** el mismo modelo congelado sobre la captura propia, con al menos ~10 mañanas entre semana (~2 semanas).
   - **Reportar `p_lgbm` al lado de `p_lgbm_sub_roll`.** En la prueba final la calibración por subgrupo no ayudó, y aquí se decide si se queda.
   - **Evaluar también el modelo de estación vacía** (`artifacts/empty/`): es su única prueba fuera de muestra.
   - Usar el mismo bootstrap por días del paso 2.
   - La recalibración semanal del subgrupo usa el Platt fijo hasta que la captura junte ~1.5 semanas de picos.
   - Con 66 días hábiles en VAL_REPORT, el IC del BSS ya mide ±0.02. Con ~10 mañanas será unas 2.5 veces más ancho (≈ ±0.05), suficiente para confirmar BSS > 0.10 pero no para medir la calibración. Para eso hacen falta más semanas.
10. **M7:** entrenar los horizontes de 10 y 20 min con la captura a 2 min.
11. **M8 / V9:** comprobar que la estación recomendada tenía lugar al llegar más veces que la más cercana. Es la prueba de que el producto funciona.

## Cómo sincronizar la captura

```sh
unset VIRTUAL_ENV                                         # si apunta a otro proyecto
eval "$(aws configure export-credentials --format env)"   # boto3 no lee las credenciales de `aws login` sin botocore[crt]
uv run python -m ecobici.ingest.captures download         # --feed station_status para un solo feed
uv run ecobici-capture-report raw/station_status
```

El bucket se lee de `S3_BUCKET_NAME` (entorno o `.env`). Solo se descargan archivos nuevos o con otro tamaño.
