# M6: LightGBM, primer modelo

Fecha: 2026-10-06. Reproducible con `uv run python -m ecobici.eval.model_report`: 5.5 min para los 3 horizontes en 14 núcleos, con 18.4 GB de RAM como máximo y DuckDB limitado a 10 GB. **Determinista:** dos corridas dan exactamente los mismos números.

## Protocolo

- **Datos:** entrenamiento 2024-09 → 2025-06 (~16.9 M ejemplos por horizonte). Parada temprana y calibración isotónica en **VAL_FIT** (2025-08, 2025-09). Las métricas salen de **VAL_REPORT** (2025-10 → 2025-12). **Los meses de prueba no se leen.**
- **Modelos:**
  - `p_lgbm`: el modelo **fijado de antemano**, con una sola calibración en VAL_FIT;
  - `p_lgbm_recal`: el mismo booster con recalibración isotónica semanal sobre los 28 días anteriores. Lo agregué al ver la calibración; es exploratorio.
- **Variables (33):**
  - estación y capacidad;
  - estado actual y de hace 15/30/60 min;
  - vecinas a ≤ 300 m;
  - hora, día, feriado y tipo de día de llegada;
  - lluvia y temperatura (Open-Meteo), ahora y la próxima hora;
  - flujo histórico de viajes (M4) en la franja de llegada y entre *t* y la llegada;
  - perfil de la estación.
  Todos los históricos se ajustan solo con entrenamiento.

## Resultado principal: saturadas en el pico (el caso del producto)

| Horizonte | Mejor línea base (persistencia calibrada) | `p_lgbm` | **BSS** |
| --- | --- | --- | --- |
| 15 min | 0.0902 | 0.0707 | **+0.216** |
| 30 min | 0.1096 | 0.0857 | **+0.218** |
| 45 min | 0.1176 | 0.0934 | **+0.205** |

En todos los cortes (todas las estaciones, pico, saturadas, saturadas + pico) y horizontes, el BSS va de **+0.17 a +0.22**.

## Metas

| Horizon | Modelo | Meta | Valor | ¿Cumple? |
|---|---|---|---|---|
| 15 min | p_lgbm | BSS > 0, all | 0.183 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, all | 0.182 | ✅ |
| 15 min | p_lgbm | BSS > 0, peak | 0.208 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, peak | 0.208 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated | 0.178 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated | 0.178 | ✅ |
| 15 min | p_lgbm | BSS > 0, saturated_peak | 0.216 | ✅ |
| 15 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.216 | ✅ |
| 15 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.059 | ❌ |
| 15 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.047 | ✅ |
| 30 min | p_lgbm | BSS > 0, all | 0.196 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, all | 0.196 | ✅ |
| 30 min | p_lgbm | BSS > 0, peak | 0.210 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, peak | 0.210 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated | 0.180 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated | 0.180 | ✅ |
| 30 min | p_lgbm | BSS > 0, saturated_peak | 0.218 | ✅ |
| 30 min | p_lgbm | BSS >= 0.1, saturated_peak | 0.218 | ✅ |
| 30 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.218 | ✅ |
| 30 min | p_lgbm_recal | BSS >= 0.1, saturated_peak | 0.218 | ✅ |
| 30 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.047 | ✅ |
| 30 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.051 | ❌ |
| 45 min | p_lgbm | BSS > 0, all | 0.196 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, all | 0.196 | ✅ |
| 45 min | p_lgbm | BSS > 0, peak | 0.196 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, peak | 0.196 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated | 0.173 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated | 0.172 | ✅ |
| 45 min | p_lgbm | BSS > 0, saturated_peak | 0.205 | ✅ |
| 45 min | p_lgbm_recal | BSS > 0, saturated_peak | 0.205 | ✅ |
| 45 min | p_lgbm | calibration gap <= 0.05, saturated_peak | 0.073 | ❌ |
| 45 min | p_lgbm_recal | calibration gap <= 0.05, saturated_peak | 0.084 | ❌ |


## Calibración: lo que falta

- **En todas las estaciones está casi perfecta:** ECE de 0.0004–0.0016, sin brecha relevante entre centro y periferia (V8 ✅).
- **Dentro de saturadas + pico, el modelo sobreestima** de 3 a 7 puntos en los rangos intermedios (0.1–0.8). La meta de ±0.05 se cumple a 30 min (0.047) y falla a 15 min (0.059) y a 45 min (0.073).
- **La recalibración móvil no lo resuelve** (15: 0.047 ✅; 30: 0.051 ❌; 45: 0.084 ❌). No es deriva en el tiempo.
- **Diagnóstico:** el calibrador isotónico se ajusta sobre todos los ejemplos, y el 97 % son casos fáciles de "no se llena". Por eso no corrige el subgrupo donde se concentra el riesgo. Es un problema de **calibración por subgrupo**.
- **Siguiente paso propuesto:** calibrar por separado el subgrupo pico + saturadas, ajustado en VAL_FIT, y confirmarlo en los meses de prueba. Como también se elige después de ver estos resultados, la prueba final decide.

## Revisión de fuga de información

- **Sin fuga:**
  - rezagos solo con lecturas pasadas (`ASOF`, t − L);
  - vecinas en el mismo instante *t*;
  - flujos y perfil de estación ajustados solo con entrenamiento;
  - calendario del día de llegada, que se conoce de antemano.
- **Ligeramente optimista:** `precip_next_hour`, porque el histórico de Open-Meteo usa el pronóstico de menor plazo. Pesa < 0.5 % de la ganancia.

## Detalles por horizonte

- **15 min:** V8 (ECE, todas las estaciones): p_lgbm: centro 0.0006, periferia 0.0004; p_lgbm_recal: centro 0.0006, periferia 0.0004. Árboles: 153; entrenamiento 1.2 min. Importancia (ganancia): docks_now 74.0%, occupancy_now 11.0%, flow_arrivals_target 2.7%, flow_departures_target 2.5%, docks_lag15 2.0%, station 1.6%, bikes_now 1.6%, flow_net_window 1.4%, docks_lag60 0.5%, nb_full_frac 0.4%, minute_of_day 0.4%, flow_net_target 0.3%, nb_occupancy_mean 0.2%, full_lag15 0.2%, docks_delta60 0.2%
- **30 min:** V8 (ECE, todas las estaciones): p_lgbm: centro 0.0012, periferia 0.0006; p_lgbm_recal: centro 0.0009, periferia 0.0007. Árboles: 137; entrenamiento 1.3 min. Importancia (ganancia): docks_now 66.9%, occupancy_now 12.2%, flow_net_window 4.1%, flow_departures_target 3.3%, station 2.6%, bikes_now 2.1%, docks_lag15 1.9%, flow_arrivals_target 1.7%, minute_of_day 1.2%, flow_net_target 0.7%, docks_lag60 0.5%, nb_full_frac 0.5%, nb_occupancy_mean 0.5%, st_full_rate 0.3%, docks_lag30 0.2%
- **45 min:** V8 (ECE, todas las estaciones): p_lgbm: centro 0.0016, periferia 0.0007; p_lgbm_recal: centro 0.0012, periferia 0.0009. Árboles: 139; entrenamiento 1.3 min. Importancia (ganancia): docks_now 62.6%, occupancy_now 11.8%, flow_net_window 6.4%, flow_departures_target 3.7%, station 3.7%, bikes_now 2.4%, docks_lag15 1.8%, minute_of_day 1.7%, flow_net_target 1.0%, flow_arrivals_target 1.0%, nb_occupancy_mean 0.6%, nb_full_frac 0.5%, docks_lag60 0.5%, st_full_rate 0.5%, target_slot 0.3%

Bugs encontrados y corregidos en M6 (con tests):
- **Columnas duplicadas:** `target_slot` y `weekend` son variables y metadatos a la vez, y salían repetidas, así que los cortes se habrían filtrado mal.
- **Resultados no reproducibles:** el orden de las filas de DuckDB cambiaba la muestra de bagging. Se arregló con `ORDER BY` y `deterministic=True`.
- **Memoria:** DuckDB usaba hasta 21 GB por el *range join* del flujo. Se cambió a sumas acumuladas y un límite de memoria con paso a disco.
