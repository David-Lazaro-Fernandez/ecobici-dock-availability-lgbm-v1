# Modelado: probabilidad de encontrar anclaje libre al llegar

Este documento explica cómo se construyó el modelo de M6, por qué se eligió cada parte de la metodología, cómo se probó y sobre qué datos. Los números vienen de los reportes de cada etapa, en [`docs/reports/`](reports/). Todo es reproducible con los comandos indicados.

Estado al 2026-10-07: **el modelo congelado cumple los criterios en la prueba final** (2026-01 y 2026-09, [M6_test](reports/M6_test.md)). Reduce el error 17–25 % frente a la mejor alternativa simple en todos los cortes. La calibración en saturadas + pico cumple en el valor puntual, sin holgura, y la calibración por subgrupo no aportó fuera de VAL_REPORT (ver [§7](#7-limitaciones-y-pendientes)).

---

## 1. El problema, en términos de modelado

El PRD pide estimar, para una estación *i* y una hora de salida, **la probabilidad de que no haya anclaje utilizable cuando la persona llegue**.

- **Tipo de problema:** **clasificación binaria probabilística**. No basta con decir "llena" o "no llena"; el recomendador usa la probabilidad *p* directamente en su puntaje (RF4: `tiempo esperado = bici + caminata + (1 − p) × costo de falla`). Por eso importan tanto la calidad de la probabilidad como su **calibración**: que un "30 %" se cumpla ~30 % de las veces.
- **Horizontes:** un modelo por horizonte (**15, 30 y 45 min**). El tiempo de viaje típico es de 12–14 min (M4), y el PRD pide varios horizontes. 10 y 20 min requieren la captura propia a 2 min y quedan para M7.
- **Qué es "llena":** instalada, aceptando devoluciones y `num_docks_available = 0`. Una estación fuera de servicio (`is_installed = 0` o `is_returning = 0`) **no** cuenta como llena: se excluye, para no confundir saturación con fallas, como pide el PRD (`ecobici.labels`).

## 2. Datos

| Fuente | Uso | Detalle |
| --- | --- | --- |
| **MaxHalford/bike-sharing-history** (CDMX) | Estado histórico de las estaciones: variables y etiquetas | Snapshot de las ~677 estaciones cada ~15 min. 16 meses sanos (2024-09 → 2026-01, sin 2025-07), 430 días cubiertos ([M2](reports/M2_history.md)) |
| **Viajes de Ecobici** (datos abiertos) | Flujo histórico por estación y franja | 50 meses, 69.1 M viajes; ≥ 99 % ligados a una estación del GBFS ([M4](reports/M4_trips.md)). Se descartan edad y género |
| **Open-Meteo** (pronóstico histórico) | Lluvia y temperatura | Horario, un punto en el centro del sistema. La misma fuente sirve para entrenar y para predecir, sin sesgo entre ambos |
| **Calendario** (`ecobici/calendar.py`) | Feriados | Feriados oficiales (LFT art. 74), más Jueves y Viernes Santos |
| **Captura propia del GBFS** (EC2, cada 2 min) | Prueba final y horizontes cortos | Corriendo desde el 2026-10-06; se usa en M7 |

**Por qué MaxHalford para entrenar y no esperar a la captura propia.** Un mes de captura propia daría pocos fines de semana y ninguna estacionalidad. MaxHalford ofrece un año completo, con dos temporadas de lluvias. La captura propia se reserva como prueba final, nunca vista por el modelo.

## 3. Cómo se construyó

### 3.1 Ejemplos y etiqueta (`ecobici.features.targets`)

Cada ejemplo es (estación, *t*, *h*):
- ***t***: una lectura de MaxHalford con la estación en servicio.
- **Etiqueta *y***: si la estación estaba llena en la **primera lectura dentro de ±7.5 min de *t + h***.
  - ±7.5 min mantiene la etiqueta dentro de una franja de 15 min, dada la cadencia de ~15 min de MaxHalford.
  - Si no hay lectura en esa ventana, el ejemplo se descarta.
  - Si la estación está fuera de servicio en ese momento, también se descarta.

Así salen ~16.9 M ejemplos de entrenamiento por horizonte.

### 3.2 Variables (`ecobici.features.model_matrix`, 33 en total)

Todas usan **solo información disponible en el instante *t***:

| Grupo | Variables | Por qué |
| --- | --- | --- |
| Estación | `station` (categórica), `capacity` | Cada estación tiene su propio patrón y tamaño |
| Estado actual | `docks_now`, `bikes_now`, `docks_disabled`, `occupancy_now` | A 15–45 min, el estado actual es la mejor señal |
| Tendencia | anclajes libres y "llena" de hace 15/30/60 min, y sus diferencias | Distingue una estación que se está llenando de una que se está vaciando |
| Vecinas a ≤ 300 m | número de vecinas, fracción llena, ocupación media, anclajes libres totales | El radio del PRD. Las vecinas fallan juntas (V6: P(B llena \| A llena) = 22.7 %, contra 2.7 % de base) |
| Calendario | minuto del día, franja de llegada, día de la semana, fin de semana, feriado (del día de **llegada**) | La saturación es fuertemente horaria ([M3](reports/M3_saturation.md)) |
| Clima | lluvia ahora y la próxima hora, temperatura | La lluvia cambia la demanda |
| Flujo histórico de viajes | llegadas, salidas y flujo neto medio en la franja de llegada; **flujo neto esperado entre *t* y la llegada** | Lo que suele pasar en esa estación a esa hora. Se calcula con sumas acumuladas por estación |
| Perfil de la estación | tasa histórica de "llena": global y en el pico | Para estaciones cuyo patrón no se ve en el estado actual |

Los perfiles históricos (flujos y perfil de estación) se ajustan **solo con los meses de entrenamiento** y luego se unen a todos los periodos. Si se ajustaran con todo el histórico, la validación se "vería" a sí misma.

### 3.3 Modelo (`ecobici.models.lgbm`)

- **Algoritmo:** **LightGBM** (gradient boosting de árboles), objetivo `binary`, un modelo por horizonte.
- **Hiperparámetros:** `learning_rate` 0.05, `num_leaves` 127, `min_data_in_leaf` 200, `feature_fraction` y `bagging_fraction` 0.8, L2 = 1. `station` es categórica.
- **Parada temprana:** 100 rondas sin mejora en el periodo VAL_FIT. Los modelos se quedan en 137–153 árboles, y cada uno entrena en ~1.3 min con 14 núcleos.
- **Calibración:** **regresión isotónica** ajustada sobre las predicciones de VAL_FIT. Es `p_lgbm`, el modelo fijado antes de ver los resultados.
- **Calibración por subgrupo:** en saturadas + pico, un Platt sobre `p_lgbm` reajustado cada semana con los 28 días anteriores del subgrupo. Si hay pocos datos, usa un Platt fijo ajustado en VAL_FIT. Es `p_lgbm_sub_roll`, **el modelo congelado para la prueba final**, elegido después de ver VAL_REPORT.
- **Reproducibilidad:** filas ordenadas (`ORDER BY sid, t`) y `deterministic=True`. Dos corridas dan exactamente los mismos números (verificado con los datos reales).

## 4. Por qué esta metodología

### 4.1 Por qué gradient boosting (LightGBM)

- **El problema es tabular y heterogéneo:** conteos, proporciones, hora, lluvia, flujos y la identidad de la estación. En datos así, los árboles de boosting son el punto de partida estándar y suelen igualar o superar a las redes neuronales con mucho menos ajuste.
- **Capturan interacciones sin programarlas**, del tipo "a las 9 h, en una estación de Polanco, con 2 anclajes libres y vecinas llenas…".
- **Aceptan valores faltantes**, como rezagos ausentes por huecos en los datos, y variables categóricas. No hace falta normalizar.
- **Escalan al volumen:** ~17 M filas por horizonte. LightGBM agrupa cada variable en intervalos (1 byte por valor) y entrena en minutos en CPU. Alternativas como el gradient boosting de scikit-learn o un random forest serían mucho más lentas con este volumen.
- **Son interpretables** con importancia por ganancia, útil para detectar errores en las variables. La variable más importante es `docks_now` (63–74 %), como se esperaba a estos horizontes; el flujo de viajes de M4 está entre las 3–4 primeras.
- **El PRD lo fija**, y deja las redes de grafos espaciotemporales solo para el caso en que el modelo tabular se estanque. No se estancó.

XGBoost o CatBoost darían resultados parecidos. CatBoost sería la comparación natural si la variable categórica `station` resultara problemática.

### 4.2 Por qué calibración isotónica, y luego Platt por subgrupo

El objetivo es una probabilidad que se pueda creer. Aunque el boosting minimiza log loss, puede quedar descalibrado cuando hay deriva entre periodos, y en M5 la vimos: el promedio histórico predecía 35 % donde se observaba 24 %. La isotónica no supone una forma funcional (a diferencia de Platt) y con millones de ejemplos no sobreajusta.

Pero la isotónica global se ajusta sobre todas las filas, y el 97 % son casos fáciles de "no se llena". En saturadas + pico, el modelo sobreestimaba 2 puntos ya en VAL_FIT y de 4 a 6 en VAL_REPORT, porque esas estaciones se llenaron menos en otoño. Para eso hay una segunda calibración, solo en el subgrupo:
- **Platt** (2 parámetros, monótono) en vez de isotónica, porque el subgrupo tiene ~20 k filas al mes y una isotónica con muchos escalones sobreajusta.
- **Reajustada cada semana** con los 28 días anteriores, porque una parte del sesgo es de temporada. Un Platt fijo en VAL_FIT corrige la parte del subgrupo, pero su IC no baja de 0.05 (0.059 / 0.058 / 0.072).

Resultado en VAL_REPORT: brecha de 0.028 / 0.029 / 0.032 a 15 / 30 / 45 min, con extremo superior del IC por días de 0.050 / 0.049 / 0.051, y el BSS sube 0.003–0.008 ([M6](reports/M6_lgbm.md#calibración-por-subgrupo-2026-10-06)). Como se eligió después de ver VAL_REPORT, la prueba final decide.

### 4.3 Por qué una separación temporal y no aleatoria

El PRD lo exige y es lo correcto: en producción siempre se predice el futuro con datos del pasado. Una mezcla aleatoria pondría en entrenamiento lecturas de 15 min antes y 15 min después de cada lectura de validación, y las métricas saldrían infladas.

### 4.4 Por qué estas líneas base

El PRD exige superar a dos (persistencia y promedio por estación y franja). Si el modelo no las supera con claridad, su complejidad no se justifica. Agregué una tercera, la **persistencia calibrada** (P(llena en *t+h* | llena ahora) por estación). La persistencia 0/1 del PRD es un rival demasiado fácil para el Brier, y la versión calibrada resultó la más fuerte de las tres ([M5](reports/M5_baselines.md)). Comparar contra ella es la prueba más exigente.

## 5. Cómo se probó

### 5.1 Protocolo de evaluación

```
2024-09 ─────────── 2025-06 │ 2025-07 │ 2025-08 ─ 09 │ 2025-10 ─── 12 │ … │ 2026-01, 2026-09
        TRAIN               │ excluido│   VAL_FIT    │   VAL_REPORT   │   │      TEST
  ajuste del modelo,        │ (datos  │ parada       │ métricas de    │   │ prueba final,
  flujos y perfiles         │ malos)  │ temprana y   │ este documento │   │ todavía SIN LEER
                            │         │ calibración  │                │   │
```

- **TRAIN** (2024-09 → 2025-06): ajuste del modelo y de todos los perfiles históricos.
- **VAL_FIT** (2025-08, 2025-09): parada temprana, calibración isotónica y el Platt fijo del subgrupo. Es la única información "del futuro" que ve el modelo, aparte de la recalibración semanal, que solo usa semanas ya pasadas.
- **VAL_REPORT** (2025-10 → 2025-12): todas las métricas reportadas. `p_lgbm` no se ajustó mirando estos meses; por eso VAL_FIT y VAL_REPORT están separados. La calibración por subgrupo (`p_lgbm_sub_roll`) sí se eligió después de verlos, y por eso la confirma TEST.
- **TEST** (2026-01, y 2026-09 desde el 11): **usados una sola vez, el 2026-10-07** ([M6_test](reports/M6_test.md)). Hasta entonces el código no leía estos archivos. 2026-01 es la prueba principal. 2026-09 se reporta aparte, porque tiene cadencia de 12 min y sus etiquetas a 15 / 30 / 45 min se leen a 12 / 24 / 48 min ([M2](reports/M2_history.md#2026-09-en-detalle-2026-10-06)).
- Los meses en que el scraper de MaxHalford se degradó (2025-07 y 2026-02 → 2026-08) quedan fuera de todo ([M2](reports/M2_history.md)).

### 5.2 Métricas y metas

Las metas se fijaron **después de medir las líneas base y antes de entrenar el modelo**, como pide el PRD. Las aprobó el dueño del producto.

| Métrica | Qué mide | Meta |
| --- | --- | --- |
| **Brier score** | Error cuadrático medio de la probabilidad. Mejor que el % de aciertos, que aquí engaña: con 2.6 % de lecturas llenas, decir siempre "hay lugar" acierta el 97.4 % | Lo más bajo posible |
| **BSS** = 1 − Brier_modelo / Brier_referencia | Mejora relativa contra **la mejor línea base de cada corte** | **> 0 en todos los cortes y horizontes**; **≥ 0.10** en saturadas + pico a 30 min |
| **Calibración** | Distancia entre predicho y observado en cada rango de probabilidad (rangos con n ≥ 1,000) | **≤ 0.05** en saturadas + pico |
| **ECE centro / periferia** (V8) | Error de calibración por zona: centro = estaciones más cerca del centroide que la mediana | Sin brechas grandes |

La explicación detallada de estas métricas está en [M5](reports/M5_baselines.md).

### 5.3 Cortes de evaluación

Una métrica global quedaría dominada por las estaciones que casi nunca se llenan (tasa base de 2.6 %). Por eso cada métrica se reporta en cuatro cortes:

| Corte | Definición | n (30 min, VAL_REPORT) | Tasa base |
| --- | --- | --- | --- |
| `all` | Todos los ejemplos | 4.78 M | 2.6 % |
| `peak` | Llegadas entre semana de 08:30 a 10:30 | 354 mil | 3.0 % |
| `saturated` | Las **114 estaciones** llenas ≥ 10 % del pico **en TRAIN** | 799 mil | 3.5 % |
| `saturated_peak` | Ambas: **el caso del producto** | 59 mil | 14.8 % |

Las estaciones saturadas se definen con datos de TRAIN, para que el corte no dependa de lo que pasó en el periodo evaluado.

### 5.4 Pruebas de software (91 tests, `uv run pytest`)

Además de la evaluación estadística, cada pieza tiene pruebas con datos sintéticos donde la respuesta correcta se conoce de antemano. Las que protegen la validez del modelo:

| Riesgo | Test |
| --- | --- |
| Etiqueta mal emparejada en el tiempo | `test_baselines.py`: la etiqueta es el estado en *t + h*; los huecos fuera de tolerancia y las lecturas fuera de servicio se descartan; se usa la franja de llegada |
| Fuga de información del futuro | `test_model_matrix.py`: los rezagos usan solo lecturas pasadas; las vecinas se toman en el mismo *t*; el perfil de estación usa solo TRAIN; los flujos se ajustan en una ventana explícita (`test_trip_features.py`) |
| Errores de calendario | Flujo entre *t* y la llegada que cruza medianoche; feriado del día de llegada; horario de verano de 2022 en los viajes |
| Vecinas mal definidas | Solo cuentan las estaciones a ≤ 300 m |
| Etiquetas incorrectas | `test_labels.py`: "fuera de servicio" tiene prioridad sobre "llena" y sobre `stale` |
| Datos de entrada sucios | `test_trips.py`: 6 formatos de nombre, 2 esquemas de columnas, años de 2 dígitos, horas dañadas, estaciones dobles |
| Modelo no reproducible | `test_lgbm.py`: dos entrenamientos dan predicciones idénticas; el orden de filas es estable |
| Recalibración que mire el futuro | `test_lgbm.py`: la recalibración semanal solo usa semanas anteriores, y con una ventana corta usa el calibrador fijo |
| Calibrador por subgrupo mal ajustado | `test_lgbm.py`: Platt recupera parámetros conocidos, es monótono y se guarda y carga igual |
| Métricas mal calculadas | `test_baselines.py::test_metrics`: Brier, BSS y calibración contra valores calculados a mano |
| Intervalos demasiado estrechos | `test_bootstrap.py`: los bloques usan el día local; con un choque que mueve a todas las estaciones el mismo día, los bloques por día dan intervalos más anchos que estación × día |
| Líneas base reajustadas con otros meses | `test_baselines.py::test_baselines_refit_on_other_months`: cada versión usa solo sus meses |
| Fuente de paquetes | `test_package_index.py`: todas las dependencias vienen de PyPI |

Estos tests encontraron bugs reales que habrían invalidado resultados:
- **Columnas duplicadas** (`target_slot` y `weekend`): los cortes del pico se habrían filtrado mal.
- **Entrenamiento no determinista:** los números cambiaban entre corridas.
- **Viajes sin hora:** se contaban como plausibles.

### 5.5 Revisión de fuga de información

Revisé variable por variable lo que se conoce en *t*:
- **Sin fuga:**
  - rezagos (`ASOF` hacia atrás);
  - vecinas (mismo snapshot);
  - flujos y perfil de estación (solo TRAIN);
  - calendario del día de llegada (se conoce de antemano).
- **Ligeramente optimista:** `precip_next_hour`. El histórico de Open-Meteo usa el pronóstico de menor plazo, un poco mejor que el que se tendría en vivo. Pesa < 0.5 % de la ganancia.

## 6. Resultados (VAL_REPORT, 2025-10 → 2025-12)

Detalle completo en [M6](reports/M6_lgbm.md). Brier del caso del producto (`saturated_peak`):

| Horizonte | Mejor línea base (persistencia calibrada) | `p_lgbm` | BSS | `p_lgbm_sub_roll` | BSS |
| --- | --- | --- | --- | --- | --- |
| 15 min | 0.0902 | 0.0707 | +0.216 | 0.0704 | **+0.219** |
| 30 min | 0.1096 | 0.0857 | +0.218 | 0.0853 | **+0.222** |
| 45 min | 0.1176 | 0.0934 | +0.205 | 0.0925 | **+0.213** |

| Meta | 15 min | 30 min | 45 min |
| --- | --- | --- | --- |
| BSS > 0 en los 4 cortes | ✅ (+0.18 … +0.22) | ✅ (+0.18 … +0.22) | ✅ (+0.17 … +0.21) |
| BSS ≥ 0.10 en saturadas + pico | n/a | ✅ +0.222 | n/a |
| Calibración ≤ 0.05 en saturadas + pico, `p_lgbm` | ❌ 0.059 | ✅ 0.047 | ❌ 0.073 |
| Calibración ≤ 0.05 en saturadas + pico, `p_lgbm_sub_roll` | ✅ 0.028 [0.018, 0.050] | ✅ 0.029 [0.021, 0.049] | ✅ 0.032 [0.025, 0.051] |
| V8: brecha centro/periferia (`p_lgbm_sub_roll`) | ✅ ECE 0.0006 / 0.0003 | ✅ 0.0012 / 0.0004 | ✅ 0.0017 / 0.0005 |

**Lectura:**
- El modelo reduce el error ~20 % frente a la mejor alternativa simple en todos los cortes, más del doble de la meta.
- **No viene de usar datos más recientes:** con las líneas base reajustadas en TRAIN + VAL_FIT, o recalibradas en VAL_FIT como el modelo, el BSS baja como mucho 0.002.
- **No es ruido:** con bootstrap por bloques de días, el IC 95 % del BSS en saturadas + pico es [+0.20, +0.23] a 15 min, [+0.20, +0.24] a 30 min y [+0.18, +0.23] a 45 min.
- **Con `p_lgbm`, la calibración en saturadas + pico no cumplía la meta de forma robusta en ningún horizonte.** El ✅ de 30 min (0.047, IC [0.039, 0.076]) no se distinguía del ❌ de 15 min (0.059, IC [0.044, 0.085]).
- **Con la calibración por subgrupo (`p_lgbm_sub_roll`) cumple en los tres**, con el extremo superior del IC por días en 0.049–0.051. Se eligió después de ver estos datos: la prueba final decide.
- La mejora viene de corregir lo que las líneas base no ven: cuando una estación saturada **todavía no** está llena a las 9 h, la persistencia calibrada predice 2.6 % de que se llene en 30 min, y en la realidad pasa el 10.8 % ([M5](reports/M5_baselines.md)).

## 7. Limitaciones y pendientes

1. **Calibración en el subgrupo saturadas + pico: cumple en la prueba final, sin holgura.**
   - En 2026-01 el modelo congelado subestima 3–7 puntos en el rango medio a 30 y 45 min, y `p_lgbm` sobreestima ~5 puntos en un bin. La calibración del subgrupo cambia de un mes a otro, y la ventana de 28 días la persigue con retraso ([M6_test](reports/M6_test.md)).
   - Si `p_lgbm_sub_roll` se queda o se vuelve a `p_lgbm` se decide en la captura propia.
   - En VAL_REPORT, la recalibración semanal global no ayudaba y la del subgrupo sí ([§4.2](#42-por-qué-calibración-isotónica-y-luego-platt-por-subgrupo)). En la prueba final, la del subgrupo queda 0.001–0.003 de BSS por debajo de `p_lgbm`: se eligió después de ver VAL_REPORT, y fuera de él no se sostuvo.
   - Necesita 28 días de etiquetas previas. En 2026-09 (sin historia antes del 11) y al inicio de la captura propia, usa el Platt fijo durante ~1.5 semanas.
   - En los bins de 0.8–0.9 (< 1,000 filas) a 30 y 45 min ahora subestima. La meta no los cuenta, pero hay que vigilarlos.
2. **Deriva entre periodos.** Octubre a diciembre de 2025 fue menos saturado que el periodo de entrenamiento. En producción, el reentrenamiento periódico con datos recientes (PRD) es la mitigación.
3. **Los viajes solo registran demanda satisfecha.** El flujo histórico subestima las llegadas a estaciones que estaban llenas. Afecta las variables, no la etiqueta, que sale del estado de la estación.
4. **Cadencia de 15 min en MaxHalford.** Episodios de "llena" más cortos pueden perderse, y por eso 10/20 min esperan a la captura propia a 2 min (M7).
5. **Una sola ubicación de clima** para todo el sistema (el área de servicio mide ~14 × 9 km, del tamaño de una celda del modelo de Open-Meteo).
6. **Todavía no se mide el producto.** Un buen Brier no garantiza buenas recomendaciones. La métrica final es **V9 (M8)**: si la estación recomendada tenía lugar al llegar, más veces que "la más cercana al destino", en simulación sobre viajes históricos.

## 8. Cómo reproducir

```sh
uv sync --all-extras
uv run python -m ecobici.ingest.maxhalford download    # 84 MB
uv run python -m ecobici.ingest.trips download         # ~5 GB de CSV → 956 MB de parquet
uv run python -m ecobici.ingest.openmeteo
uv run python -m ecobici.eval.baseline_report           # M5, ~15 s
uv run python -m ecobici.eval.model_report              # M6, ~7 min, ~18 GB de RAM como máximo
uv run pytest
```

Los modelos se guardan en `artifacts/lgbm_{h}.txt`, su calibración en `artifacts/isotonic_{h}.json` y el Platt fijo del subgrupo en `artifacts/platt_sub_{h}.json`; todos están en `.gitignore`.
