# M5: Líneas base

Fecha: 2026-10-06. Reproducible con `uv run python -m ecobici.eval.baseline_report` (14 s, ~8.5 GB de RAM como máximo).

## Diseño

- **Ejemplos:** cada lectura de MaxHalford (estación, *t*) con la estación en servicio. La etiqueta es "llena" en la primera lectura a ±7.5 min de *t + h*; si en ese momento está fuera de servicio, el ejemplo se descarta.
- **Separación temporal:** entrenamiento 2024-09 → 2025-06; **evaluación en validación**, 2025-08 → 2025-12. **Los meses de prueba (2026-01 y 2026-09) no se leen.**
- **Líneas base:** todas ajustadas solo con entrenamiento.
  - `p_persist`: "seguirá como está", 0/1, la definición del PRD.
  - `p_persist_cal`: persistencia calibrada, P(llena en *t+h* | llena ahora) por estación, con respaldo global.
  - `p_hist`: promedio por estación × franja de llegada × tipo de día, con respaldo por estación y global.
- **Cortes:**
  - `all`: todos los ejemplos;
  - `peak`: llegadas entre semana de 08:30 a 10:30;
  - `saturated`: las **114 estaciones** llenas ≥ 10 % del pico en entrenamiento;
  - `saturated_peak`: ambas condiciones.

## Resultados (validación)

| Horizon | Segment | n | Base rate | Model | Brier | Log loss |
|---|---|---|---|---|---|---|
| 15 min | all | 7,958,239 | 0.026 | p_persist | 0.0120 | 0.1658 |
| 15 min | all | 7,958,239 | 0.026 | p_persist_cal | 0.0100 | 0.0452 |
| 15 min | all | 7,958,239 | 0.026 | p_hist | 0.0226 | 0.0992 |
| 15 min | peak | 584,788 | 0.033 | p_persist | 0.0257 | 0.3545 |
| 15 min | peak | 584,788 | 0.033 | p_persist_cal | 0.0206 | 0.0836 |
| 15 min | peak | 584,788 | 0.033 | p_hist | 0.0278 | 0.1071 |
| 15 min | saturated | 1,331,934 | 0.038 | p_persist | 0.0301 | 0.4154 |
| 15 min | saturated | 1,331,934 | 0.038 | p_persist_cal | 0.0236 | 0.1007 |
| 15 min | saturated | 1,331,934 | 0.038 | p_hist | 0.0334 | 0.1351 |
| 15 min | saturated_peak | 97,850 | 0.163 | p_persist | 0.1248 | 1.7246 |
| 15 min | saturated_peak | 97,850 | 0.163 | p_persist_cal | 0.1000 | 0.3767 |
| 15 min | saturated_peak | 97,850 | 0.163 | p_hist | 0.1344 | 0.4308 |
| 30 min | all | 7,998,759 | 0.026 | p_persist | 0.0163 | 0.2254 |
| 30 min | all | 7,998,759 | 0.026 | p_persist_cal | 0.0129 | 0.0567 |
| 30 min | all | 7,998,759 | 0.026 | p_hist | 0.0225 | 0.0993 |
| 30 min | peak | 584,108 | 0.033 | p_persist | 0.0323 | 0.4459 |
| 30 min | peak | 584,108 | 0.033 | p_persist_cal | 0.0248 | 0.0998 |
| 30 min | peak | 584,108 | 0.033 | p_hist | 0.0278 | 0.1071 |
| 30 min | saturated | 1,338,701 | 0.038 | p_persist | 0.0388 | 0.5357 |
| 30 min | saturated | 1,338,701 | 0.038 | p_persist_cal | 0.0281 | 0.1185 |
| 30 min | saturated | 1,338,701 | 0.038 | p_hist | 0.0331 | 0.1346 |
| 30 min | saturated_peak | 97,734 | 0.163 | p_persist | 0.1568 | 2.1658 |
| 30 min | saturated_peak | 97,734 | 0.163 | p_persist_cal | 0.1206 | 0.4462 |
| 30 min | saturated_peak | 97,734 | 0.163 | p_hist | 0.1344 | 0.4308 |
| 45 min | all | 8,068,810 | 0.025 | p_persist | 0.0192 | 0.2650 |
| 45 min | all | 8,068,810 | 0.025 | p_persist_cal | 0.0146 | 0.0636 |
| 45 min | all | 8,068,810 | 0.025 | p_hist | 0.0221 | 0.0986 |
| 45 min | peak | 594,207 | 0.032 | p_persist | 0.0348 | 0.4810 |
| 45 min | peak | 594,207 | 0.032 | p_persist_cal | 0.0267 | 0.1077 |
| 45 min | peak | 594,207 | 0.032 | p_hist | 0.0277 | 0.1069 |
| 45 min | saturated | 1,350,472 | 0.037 | p_persist | 0.0434 | 0.5989 |
| 45 min | saturated | 1,350,472 | 0.037 | p_persist_cal | 0.0299 | 0.1262 |
| 45 min | saturated | 1,350,472 | 0.037 | p_hist | 0.0325 | 0.1328 |
| 45 min | saturated_peak | 99,428 | 0.161 | p_persist | 0.1678 | 2.3187 |
| 45 min | saturated_peak | 99,428 | 0.161 | p_persist_cal | 0.1300 | 0.4792 |
| 45 min | saturated_peak | 99,428 | 0.161 | p_hist | 0.1333 | 0.4281 |


### Calibration, p_persist_cal, 30 min, saturated_peak
| Bin | n | Predicted | Observed |
|---|---|---|---|
| 0 | 84,814 | 0.026 | 0.108 |
| 3 | 1,856 | 0.371 | 0.397 |
| 4 | 6,413 | 0.455 | 0.462 |
| 5 | 3,255 | 0.543 | 0.631 |
| 6 | 1,321 | 0.644 | 0.724 |
| 7 | 75 | 0.722 | 0.547 |

### Calibration, p_hist, 30 min, saturated_peak
| Bin | n | Predicted | Observed |
|---|---|---|---|
| 0 | 14,004 | 0.049 | 0.050 |
| 1 | 28,229 | 0.155 | 0.100 |
| 2 | 24,224 | 0.247 | 0.144 |
| 3 | 18,478 | 0.346 | 0.237 |
| 4 | 10,083 | 0.445 | 0.332 |
| 5 | 2,505 | 0.536 | 0.418 |
| 6 | 211 | 0.642 | 0.483 |

## Lectura

- **La línea base a vencer es la persistencia calibrada.** Tiene el menor Brier en todos los cortes y horizontes. El promedio histórico solo se le acerca a 45 min en `saturated_peak` (0.1333 contra 0.1300) y ahí gana en log loss. La persistencia 0/1 del PRD es la más débil: al dar 0 o 1, castiga mucho el log loss.
- **El promedio histórico está mal calibrado en validación.** En `saturated_peak` predice ~0.35 donde se observa ~0.24, porque agosto a diciembre de 2025 fue menos saturado que el entrenamiento. Hay **deriva entre periodos**: el modelo necesita el estado actual y reciente, y la calibración debe ajustarse con datos recientes.
- **El margen para el modelo está en "todavía no está llena, pero se va a llenar".** En `saturated_peak` a 30 min, cuando la estación no está llena, la persistencia calibrada predice 2.6 % y se observa **10.8 %**. Promedia todas las horas del día; LightGBM puede condicionar en la hora, los anclajes libres, la tendencia y las vecinas.

## Metas numéricas para M6 (aprobadas el 2026-10-06)

El PRD dejaba las metas para después de medir las líneas base. La referencia es, en cada corte, **la mejor línea base de ese corte**.

| Métrica | Meta |
| --- | --- |
| BSS contra la mejor línea base, en todos los cortes y horizontes | **> 0** |
| BSS en `saturated_peak`, 30 min (el caso del producto) | **≥ 0.10**, es decir Brier ≤ 0.1085 |
| Calibración en `saturated_peak`, bins con n ≥ 1,000 | \|observado − predicho\| ≤ 0.05 |
| Brecha centro/periferia (V8) | Se mide en M6 con la misma calibración |

Aprobadas por @Dave el 2026-10-06. La métrica de producto definitiva es V9 (M8): si BSS queda algo por debajo de 0.10, se decide después de ver su efecto en las recomendaciones.
