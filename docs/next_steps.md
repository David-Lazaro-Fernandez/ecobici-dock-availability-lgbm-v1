# Siguientes pasos: del modelo M6 a la prueba final

Estado al 2026-10-06, actualizado tras cerrar los pasos 1 y 2. Resume la revisión de [`modeling.md`](modeling.md) y lo que se decidió después de revisar la captura propia. Los plazos y las etapas generales siguen en [`ENG_PLAN.md`](ENG_PLAN.md).

## Dónde estamos

- **M6, precisión:** en VAL_REPORT (2025-10 → 2025-12), LightGBM reduce el Brier ~20 % frente a la mejor línea base en todos los cortes y horizontes (BSS +0.17 … +0.22).
  - **Es del modelo:** con líneas base que ven los mismos datos (TRAIN + VAL_FIT), el BSS baja como mucho 0.002.
  - **No es ruido:** en saturadas + pico, el IC 95 % por días es [+0.20, +0.23] a 15 min, [+0.20, +0.24] a 30 min y [+0.18, +0.23] a 45 min.
  - El log loss baja ~35 %.
- **M6, calibración en saturadas + pico:** no cumple la meta (≤ 0.05) de forma robusta en ningún horizonte.
  - 15 min: 0.059 [0.044, 0.085]; 30 min: 0.047 [0.039, 0.076]; 45 min: 0.073 [0.054, 0.107].
  - El ✅ de 30 min no se distingue del ❌ de 15 min.
  - El problema es un sesgo sistemático: el modelo sobreestima en los bins intermedios, y los intervalos no tocan la diagonal. Detalle en [M6](reports/M6_lgbm.md#calibración-lo-que-falta).
- **Captura propia:** corre desde el 2026-10-06. El primer día solo tiene ~3 h continuas (11:37–14:38 hora local), sin pico de la mañana. Todavía no sirve para medir el modelo.
- **Meses de prueba de MaxHalford** (2026-01 y 2026-09): sin leer. Con ellos ya se puede obtener el resultado final de 15, 30 y 45 min, sin esperar a la captura.

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
3. **Calibración por subgrupo (saturadas + pico).** Es ahora el paso más importante: es lo único que no cumple la meta.
   - Ajustar un calibrador propio del subgrupo en VAL_FIT, revisarlo en VAL_REPORT con los IC del paso 2 y congelarlo.
   - **Criterio de éxito:** la brecha baja y su IC por días queda bajo 0.05, en los tres horizontes, sin perder BSS.
   - Ojo: en VAL_FIT el subgrupo es chico (~2 meses de mañanas entre semana en ~100 estaciones). Preferir un calibrador simple (Platt o isotónica con pocos escalones) a uno que sobreajuste.
   - **No elegir el calibrador mirando TEST.**
4. **Septiembre de 2026.** M2 lo marca ❌ (72 huecos de más de 1 h). Decidir si se filtran los huecos o se excluye el mes. Reportarlo separado de 2026-01.
5. **Pipeline de evaluación sobre la captura.** GBFS JSON → las mismas 33 variables → predicciones → métricas. Probarlo solo en la ventana del 2026-10-06, 11:37–14:38 hora local (17:37–20:38 UTC). Esa ventana queda marcada como *dev* y fuera de la prueba final para siempre.

### Mientras corre la captura (2–4 semanas)

6. **Revisar la salud de la captura cada pocos días** (ver [Cómo sincronizar](#cómo-sincronizar-la-captura)). Un hueco como el del primer día (105 min) no debe repetirse en las mañanas entre semana.
7. *(Opcional)* Agregar `botocore[crt]` al extra `collector`, desde PyPI, para no tener que exportar credenciales.

### Después, una sola vez

8. **Prueba final de 15, 30 y 45 min:** congelar el modelo y evaluarlo en 2026-01 y 2026-09. Se puede hacer apenas terminen los pasos 1–4.
9. **Prueba en datos reales:** el mismo modelo congelado sobre la captura propia, con al menos ~10 mañanas entre semana (~2 semanas).
   - Usar el mismo bootstrap por días del paso 2.
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
