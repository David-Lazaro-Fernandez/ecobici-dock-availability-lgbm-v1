# Plan de ejecución de ingeniería — Recomendador de estación destino Ecobici CDMX

Basado en [`PRD.md`](PRD.md) (Oct 6, 2026). Fecha del plan: 2026-10-06.

## 0. Hechos verificados hoy (cambian el plan)

| Tema | PRD decía | Medido el 2026-10-06 |
| --- | --- | --- |
| Feed GBFS (V3) | Versión, campos y licencia sin verificar | Responde. Sin campo `version` (formato GBFS 1.x). `ttl: 10` confirmado. `license_url` vacío. `start_date` 2022-06-19, zona `GMT-06:00`. 677 estaciones. |
| Campos para "llena" / "fuera de servicio" | Por confirmar | `station_status`: `num_docks_available`, `num_docks_disabled`, `is_installed`, `is_renting`, `is_returning`, `last_reported`. `station_information`: `capacity`, `lat`, `lon`, `short_name` (p. ej. "710" = CE-710). **Suficiente para V3.** |
| Estado en una captura | — | 36/677 (5.3 %) con 0 anclajes; 17 con `is_returning=0`; 13 con anclajes deshabilitados; 21 con `last_reported` de más de 1 h (una con ~99 días). |
| MaxHalford: inicio CDMX (V4) | Riesgo: "empieza después de ago 2022" | Archivo parquet desde **2024-04**. Hueco de may a jul de 2024. |
| MaxHalford: frecuencia | Sin medir | Snapshots completos (~678 filas/commit). Mar 2025: mediana de 15.6 min. Sep 2026: 12.0 min. **Jul 2026: mediana de 90 min (inservible).** Los meses débiles son 2024-04/08, 2025-07 y 2026-02 a 2026-08. |
| MaxHalford: timestamp | — | Solo `committed_at_utc`; **no trae `last_reported`**. |
| MaxHalford: clima | "Histórico de clima" | Es **pronóstico** a 24 h, capturado cada hora, no clima observado. |
| MaxHalford: licencia | Por revisar | El repo **no declara licencia** (por defecto, todos los derechos reservados). Tiene `CITATION.cff`. |

## 1. Veredicto de la revisión

**Sí se puede empezar**, con las etapas 1 y 2 del PRD. Están desbloqueadas, V3 está prácticamente resuelta y V4 parcialmente. El PRD está bien estructurado: tiene etapas con condición, líneas base obligatorias y validación temporal. No hace falta reescribirlo para arrancar.

Antes de la **etapa 4 (modelo)** hay que cerrar las decisiones de la sección 2. Antes de **publicar o comercializar** hay que cerrar las licencias.

## 2. Hallazgos de la revisión

### Bloquean la etapa 4: decidir antes de modelar

1. **Definición exacta de la variable objetivo.** Propuesta:
   - `llena = num_docks_available == 0` con `is_installed=1 AND is_returning=1`.
   - `no_disponible = is_installed=0 OR is_returning=0`. Es otra clase: se excluye del entrenamiento de "llena" y del recomendador (RF7).
   - Lecturas con `last_reported` más viejo que X min (propuesta: 30) se marcan `stale` y no generan etiqueta.
   - *Actualización 2026-10-06:* "no disponible" tiene prioridad sobre `stale`; las 17 estaciones fuera de servicio llevaban horas sin reportar. Además, las estaciones parecen reportar solo cuando cambian: 43 de 70 "stale" tenían 30–60 min sin reportar y 50 de 70 estaban sin bicis. Con 30 min se descartarían lecturas válidas de estaciones tranquilas. El umbral se revisa con el reporte V2 de M1.
   - Variante a evaluar: `≤ 1 anclaje`, como margen por llegadas simultáneas.
2. **El clima de MaxHalford es pronóstico, no observación.** Esto choca con la decisión "MaxHalford para entrenar, Open-Meteo para predecir". Recomendación: usar la **API de pronósticos históricos de Open-Meteo** (ya citada en el PRD) tanto para entrenar como para predecir. Elimina el sesgo entre entrenamiento y uso, y la V5 deja de ser necesaria. Es una decisión ya tomada en el PRD, así que la tiene que aprobar el dueño del producto.
3. **Frecuencia de captura propia: 2 minutos (recomendado).** Medición del 2026-10-06, con 6 lecturas a 1 min: en cada minuto ~136 de 677 estaciones (~20 %) envían un `last_reported` nuevo, o sea que cada estación reporta en promedio cada ~5 min. Con 1 min, la mayoría de las lecturas repiten el dato anterior. Con 2 min, el desfase máximo entre el reporte de la estación y nuestra lectura es de 2 min, aceptable para horizontes de 10 min o más. Además se guarda el `last_reported` de cada estación, así que el momento real del dato no se pierde. Cada request pesa unos 166 KB: son 720 requests al día, unos 120 MB crudos (unos 12 MB con gzip). Con 5 min no se ve bien el horizonte de 10 min.
4. **Dos frecuencias distintas.** MaxHalford va a 12–16 min y la captura propia a 2 min. Los rezagos ("ocupación hace 5 min") no existen en MaxHalford. Propuesta: construir las variables sobre una rejilla común de 15 min para el modelo que mezcla fuentes. Horizontes de **15, 30 y 45 min** con MaxHalford; 10 y 20 min solo con la captura propia.

### Importantes, no bloquean el arranque

5. **El puntaje RF4 ignora el respaldo.** Si la principal está llena, el costo real es el desvío al respaldo, no una constante. Propuesta:
   `E[t] = t_bici + (p₁)·t_camina₁ + (1−p₁)·[t_desvío₁→₂ + t_camina₂ + (1−p₂|₁ llena)·C]`.
   Así el "costo de falla" C solo aplica cuando fallan ambas, y RF6 entra al puntaje.
6. **Brier con clases desbalanceadas.** Con una tasa base cercana al 5 %, un Brier bajo es fácil de lograr. Reportar el **Brier skill score** contra cada línea base, y un Brier estratificado por estaciones que se llenan a menudo.
7. **Métricas frente a V9.** La tabla de métricas compara solo contra "la más cercana". V9 también compara contra "más anclajes libres al salir". Usar las dos en ambas.
8. **Llave entre viajes y GBFS.** Los viajes usan nombres o códigos de estación ("CE-710"). Hay que mapearlos a `station_id` vía `short_name`; está pendiente verificar la cobertura del mapeo.
9. **"500 m a pie" sin servicio de rutas.** Usar distancia haversine × factor de desvío (propuesta: 1.3) y documentarlo como supuesto.
10. **Zona horaria.** UTC en almacenamiento; `America/Mexico_City` (sin horario de verano desde 2022) para las variables. Calendario de feriados oficiales de México.
11. **Infraestructura del colector.** Un mes de captura continua no puede depender de una laptop. Hace falta un host 24/7 con alertas de huecos (ver la sección 4).

### Antes de publicar o comercializar

12. **Licencias.** El GBFS no declara licencia (`license_url` vacío) y MaxHalford tampoco. Uso interno o de investigación: razonable, con atribución. Redistribuir datos derivados o uso comercial: pedir permiso, o depender solo de la captura propia. Open-Meteo gratis es solo no comercial.
13. **Responsables: "por definir".** Asignar al menos un responsable del colector y uno del modelo.

### Correcciones al PRD sugeridas

- El riesgo "el histórico externo empieza después de agosto 2022" ya se puede precisar: empieza en 2024-04 y es útil desde 2024-09, con huecos conocidos.
- Con ~16 meses útiles de MaxHalford, el PRD subestima el histórico disponible. **La etapa 4 no necesita esperar al mes de captura propia** (ver la sección 3).
- V3: marcar como cumplida, salvo la licencia.

## 3. Plan por hitos

El cambio principal frente al PRD es que la etapa 4 arranca **en paralelo** con la captura, usando MaxHalford. La captura propia se usa después como bloque de prueba final, nunca visto por el modelo, y para los horizontes cortos.

| Hito | Fechas (propuesta) | Entregable | Condición de salida |
| --- | --- | --- | --- |
| **M0 Andamiaje** | 6–7 oct | Repo con `uv`, estructura, CI de lint y tests, `docs/` | `uv run pytest` en verde |
| **M1 Colector + validación de captura** (etapa 1) | 7–10 oct | Colector a 2 min en EC2 + S3. Guarda JSON crudo con gzip, `station_information` diaria y alerta de huecos. | 3 días con más del 99 % de minutos capturados. Reporte V2 (huecos, duplicados, `stale`). Se reconstruye la etiqueta. |
| **M2 Diagnóstico del histórico externo** (etapa 2) ✅ [reporte](reports/M2_history.md) | 6 oct | Notebook o script V4: cobertura mensual, cadencia y meses usables. Consolidación en parquet local. Clima histórico de Open-Meteo descargado. | Lista de meses usables. Decisión de clima tomada (hallazgo 2). |
| **M3 V1 + V6 sobre MaxHalford** ✅ [reporte](reports/M3_saturation.md) | 6 oct | % de lecturas llenas por estación × franja de 15 min. P(B llena \| A llena) para vecinas a ≤ 500 m. | **Go/no-go del producto.** Si la saturación es rara, se replantea antes de invertir más. |
| **M4 Viajes** (etapa 3, parte de limpieza) ✅ [reporte](reports/M4_trips.md) | 6 oct | Ingesta de viajes desde ago 2022 con nombres y fechas normalizados. Mapeo a `station_id`. Flujo neto por estación × franja. Duración por par × hora. | Más del 95 % de los viajes mapeados a una estación GBFS |
| **M5 Líneas base** ✅ [reporte](reports/M5_baselines.md) | 6 oct | Persistencia y promedio por estación × franja de 15 min. Separación temporal: entrena hasta jun 2025, valida ago–dic 2025, prueba ene 2026 y sep 2026. | Brier, Brier skill score y calibración de las líneas base registrados. **Se fijan las metas numéricas del PRD.** |
| **M6 LightGBM v1** (etapa 4) 🟡 [reporte](reports/M6_lgbm.md): BSS ✅, calibración por subgrupo pendiente | 6 oct → | Variables de la sección del PRD. Horizontes de 15, 30 y 45 min. Calibración (isotónica o Platt sobre validación). | V7: supera ambas líneas base con claridad. V8: calibración por centro y periferia. |
| **M7 Captura de 1 mes cerrada** | ~10 nov | 1 mes a 2 min | Evaluación del modelo M6 en este bloque sin reentrenar. Horizontes de 10 y 20 min entrenados con la captura propia. |
| **M8 Recomendador offline** (etapa 5) | 16–27 nov | Puntaje de tiempo esperado (con el ajuste del hallazgo 5). Simulador V9 sobre viajes históricos y estados capturados. | V9: más aciertos que "la más cercana" y que "más anclajes al salir" |
| **M9 Cierre de la fase 1** | 30 nov – 4 dic | Reporte de métricas y decisión sobre la fase de API y la fase 2 | Métricas del PRD cumplidas o decisión documentada |

Hay dos colchones de calendario: el mes de captura incluye Día de Muertos (2 nov) y el feriado de Revolución (16 nov). Las semanas atípicas también son útiles para el bloque de prueba.

## 4. Arquitectura propuesta (fase 1, sin API)

```
                ┌──────────────────────────┐
 GBFS (2 min) ─▶│ collector (cron/loop)    │──▶ raw/station_status/YYYY/MM/DD/HHMM.json.gz
                │ + station_information/día │──▶ raw/station_information/YYYY-MM-DD.json.gz
                └────────────┬─────────────┘
                             │ heartbeat / alertas de huecos
 MaxHalford parquet ─┐       ▼
 Open-Meteo hist. ───┼─▶ ingest/ ─▶ data/curated/*.parquet  (UTC, schema único, flags stale/no_disponible)
 Viajes Ecobici ─────┘                    │
                                          ▼
                              features/ ─▶ data/features/*.parquet  (rejilla 15 min + 2 min)
                                          │
                              models/  (baselines, lgbm, calibración) ─▶ artifacts/
                                          │
                              eval/   (Brier, BSS, calibración, V1/V6/V9 simulador)
```

- **Stack:** Python 3.12, `uv`, `duckdb` + parquet, `polars` (pandas prohibido por `ruff`, regla TID251), `lightgbm`, `scikit-learn` (calibración y métricas), `pytest`.
- **Host del colector (decidido):** EC2 pequeña (`t4g.nano` o `t4g.micro` alcanzan) con un timer de systemd. Guarda en S3 con un rol IAM restringido a `s3:PutObject` en el bucket. Una alarma de CloudWatch avisa si pasan más de 10 min sin escritura. GitHub Actions no sirve: su cron tiene mínimo de 5 min y no es puntual.
- **Datos crudos inmutables.** Todo lo derivado se puede regenerar desde `raw/`.
- **Datos personales:** no se ingieren edad ni género de los viajes (se descartan en la ingesta).

### Estructura del repo

```
src/ecobici/
  collector/    # captura GBFS
  ingest/       # gbfs_raw, maxhalford, openmeteo, trips
  features/
  models/       # baselines.py, lgbm.py, calibrate.py
  eval/         # metrics.py, splits.py, simulate.py
  recommender/  # scoring.py (offline)
scripts/        # CLIs de cada etapa
notebooks/      # diagnósticos V1–V6 (solo lectura de data/)
tests/
docs/           # PRD.md, ENG_PLAN.md, decisiones (ADR)
```

## 5. Decisiones

Aprobadas por @Dave el 2026-10-06:

1. ✅ Definición de "llena", "no disponible" y "stale" del hallazgo 1.
2. ✅ Clima: pronóstico histórico de Open-Meteo para entrenar y para predecir. Reemplaza la decisión del PRD; V5 queda sin efecto.
3. ⏳ Frecuencia de captura: **2 min** recomendado (ver el hallazgo 3), pendiente de confirmar.
4. ✅ Horizontes de 15, 30 y 45 min con MaxHalford; 10 y 20 min solo con la captura propia.
5. ✅ Colector en una instancia **EC2** que guarda en **S3** (sección 4).
6. ✅ Puntaje con respaldo integrado (hallazgo 5) en lugar de RF4 tal cual.

Pendiente: responsables del colector y del modelo.
