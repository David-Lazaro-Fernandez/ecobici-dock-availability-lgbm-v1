# Ciclo en vivo: captura, predicción, registro y evaluación

Este documento es el mapa del ciclo que mide el modelo con datos reales. Dice qué pieza hace cada paso, dónde está en el código y qué falta. El modelo y su entrenamiento están en [`metodologia.md`](metodologia.md) y [`modeling.md`](modeling.md). Los pasos y las decisiones están en [`next_steps.md`](next_steps.md).

Estado al 2026-10-08.

## Resumen

```text
GBFS de Ecobici
   │  cada 2 min (EC2, systemd)
   ▼
s3://<bucket>/raw/<feed>/…            ← captura propia
   │  la API lee los últimos minutos
   ▼
API en OCI (/v1/stations, /v1/plan)   ← predicción en vivo
   │                     ▲
   │ plan, feedback      │ búsqueda y plan
   ▼                     │
s3://<bucket>/plans/…    web/ (Vercel)
s3://<bucket>/feedback/…
   │  descarga a la laptop
   ▼
evaluación offline                    ← paso 9, reporte semanal (pendientes)
   │
   ▼
web/public/lugares.json               ← lugares nuevos para la búsqueda
```

El bucket es `ecobici-dock-availability` (us-east-1). Las rutas del código son relativas a la raíz del repo.

## 1. Captura

| Qué | Dónde |
| --- | --- |
| Colector (descarga, valida y guarda el JSON crudo) | `src/ecobici/collector/capture.py`, CLI `ecobici-capture` (`collector/cli.py`) |
| Destino local o S3 | `src/ecobici/collector/sinks.py` (`LocalSink`, `S3Sink`, `sink_from_uri`) |
| Llave en S3 | `raw/<feed>/YYYY/MM/DD/<feed>_YYYYMMDDTHHMMSSZ.json.gz`, en UTC (`capture.object_key`) |
| Servidor y timers | `deploy/ec2/` (`station_status` cada 2 min; `station_information` y `system_information` una vez al día) |
| Salud de la captura | `ecobici-capture-report` (`collector/report.py`): huecos y cobertura de las mañanas entre semana |

## 2. Predicción en vivo

| Qué | Dónde |
| --- | --- |
| Captura → las mismas 33 variables → probabilidades | `src/ecobici/live.py` (`capture_rows`, `predict`, `load_frozen`) |
| Servicio: lee S3 cada minuto, guarda el estado actual | `src/ecobici/serve.py` (`LiveService.current`, `LiveService.plan`) |
| Planificador (estación de partida, candidatas, tiempo esperado) | `src/ecobici/recommender/plan.py` |
| Paquete de servicio (tablas precalculadas que lee la API) | `src/ecobici/bundle.py` → `artifacts/serving/` |
| HTTP | `src/ecobici/api.py`: `/health`, `/v1/stations`, `/v1/plan`, `POST /v1/feedback` |
| Servidor | `deploy/api/` (OCI, Caddy, auto-deploy desde `main`). Un merge a `main` es un deploy: ver `AGENTS.md` |

Las predicciones no se guardan en la API. El modelo es determinista y el paquete da las mismas probabilidades que el código completo, así que la evaluación las vuelve a calcular a partir de la captura.

## 3. Lo que piden las personas

### Búsqueda en la web

| Qué | Dónde |
| --- | --- |
| Búsqueda local (estaciones + `lugares.json`) y en línea (Photon) | `web/lib/places.ts` (`buildIndex`, `searchPlaces`, `geocode`, `merge`) |
| Origen de cada sugerencia (`source`: `station`, `index`, `photon`, `address`) | `web/lib/places.ts` (`Source`, `toSuggestion`) |
| Índice de lugares | `web/public/lugares.json`, generado por `scripts/export_places.py` (Overpass, a mano) |
| Petición del plan, `plan_id` y campos del lugar | `web/components/planner.tsx` (`placeParams`, `planParams`, `requestParams`) |
| Preguntas de feedback | `web/components/feedback.tsx`, `web/lib/feedback.ts` |

### Registro de planes

| Qué | Dónde |
| --- | --- |
| Registro y reglas de privacidad | `src/ecobici/plans.py` |
| Armado del registro en la API | `src/ecobici/api.py` (`plan_record`, `save_plan`) |
| Destino | `ECOBICI_PLAN_SINK` (en el servidor, `s3://<bucket>/plans`). Sin la variable, no se guarda nada |
| Llave | `plans/YYYY/MM/DD/<plan_id>.json.gz`, con la fecha local de la captura |
| Permiso IAM | `deploy/api/iam-policy.json` (`WritePlans`) |
| Pruebas | `tests/test_api.py` (`test_a_plan_is_saved_once…`, `test_a_private_end…`), `web/e2e/search.spec.ts` |

Reglas:

- Se guarda la primera respuesta de cada `plan_id`. La web pide el mismo plan cada minuto.
- Máximo 120 planes guardados por hora por cliente. Los siguientes se responden, pero no se guardan.
- Solo un lugar público (`station`, `index`, `photon`) guarda su nombre y sus coordenadas.
- Una dirección, un punto del mapa o la ubicación del dispositivo (`address`, `map`, `location`) no guarda nombre ni coordenadas. Sus distancias se cambian por `walk_order`, porque las distancias a tres estaciones dan el punto exacto.
- No se guarda el texto escrito ni la IP.

### Feedback

| Qué | Dónde |
| --- | --- |
| Registro y límite por cliente | `src/ecobici/feedback.py` |
| Destino | `ECOBICI_FEEDBACK_SINK` (en el servidor, `s3://<bucket>/feedback`) |
| Llave | `feedback/YYYY/MM/DD/<plan_id>_<kind>.json.gz` (`kind`: `rating` o `trip`) |

El plan y sus respuestas se unen por `plan_id`.

## 4. Evaluación offline

Se corre en la laptop. Descargar primero:

```sh
uv run --extra api python -m ecobici.ingest.captures download   # raw/ (solo archivos nuevos)
uv run python -m ecobici.ingest.capture_snapshots               # data/own/snapshots/, un parquet por día
```

| Qué | Dónde | Estado |
| --- | --- | --- |
| Captura → parquet con el esquema de MaxHalford, sin lecturas `stale` | `src/ecobici/ingest/capture_snapshots.py` | Hecho |
| Modelos de 5 y 10 min sobre la captura (apilados sobre el de 15) | `src/ecobici/eval/short_report.py` | Hecho. Corre en seco hasta tener 5 días entre semana de reporte (`MIN_REPORT_WEEKDAYS`) |
| Métricas y bootstrap por días | `src/ecobici/eval/metrics.py`, `src/ecobici/eval/bootstrap.py` | Hecho, se reutilizan |
| **Paso 9:** modelo congelado de 15/30/45 min y de estación vacía sobre la captura, `p_lgbm` contra `p_lgbm_sub_roll` | Falta. `model_report.py` y `test_report.py` solo leen MaxHalford | Pendiente: ~10 mañanas entre semana (≈ 2026-10-20) |
| **Reporte semanal de planes:** demanda, precisión en los planes pedidos, recomendada contra más cercana (V9), lugares de Photon | Falta | Pendiente: necesita planes guardados |
| Cruce del feedback con la captura | Falta | Pendiente |

Para descargar los planes y el feedback, no hay comando todavía. `ingest/captures.py` solo descarga `raw/`.

## 5. Consultar los registros

Decisión (2026-10-08): no se usa OpenSearch. Los registros tienen campos fijos y poco volumen (~1 KB por plan, ~0.2 KB por respuesta), y las preguntas importantes cruzan los planes con la captura.

- **Análisis y reporte:** DuckDB sobre los `.json.gz`. `plan_id` se lee como UUID: usar `plan_id::varchar` para compararlo con texto.

  ```sql
  select "to".kind, "to".name, count(*) as plans
  from read_json_auto('plans/**/*.json.gz', union_by_name = true)
  group by all order by plans desc;

  -- Una fila por estación candidata de cada plan.
  select plan_id, c.id, c.rank, c.walk_order, c.p_free, c.arrive_at
  from read_json_auto('plans/**/*.json.gz', union_by_name = true), unnest(candidates) as t(c);
  ```

- **Página `/admin`:** en `https://ecobici-docks.duckdns.org/admin`. Pestañas: demanda, lugares de Photon, feedback, lista de planes y SQL.

  | Qué | Dónde |
  | --- | --- |
  | Copia desde S3, tablas de DuckDB y vistas | `src/ecobici/admin.py` (`Admin`, `sync`, `load`) |
  | Rutas `/admin` y `/admin/api/*` | `src/ecobici/admin_routes.py` |
  | Página | `src/ecobici/admin.html` (HTML y JavaScript, sin recursos externos) |
  | Pruebas | `tests/test_admin.py` |
  | Puesta en marcha | `deploy/api/README.md`, sección 6 |

  - Solo existe con `ECOBICI_ADMIN=on`. La API no pide contraseña: Caddy protege `/admin*` con `basic_auth`, y la API escucha solo en `127.0.0.1`.
  - La API copia `plans/` y `feedback/` a `ECOBICI_ADMIN_DIR` (en el servidor, `/opt/ecobici/data/logs/`) como mucho cada 2 min. Necesita `ListLogs` y `ReadLogs` en IAM.
  - Tablas: `plans`, `candidates`, `pickups`, `feedback`, `stations`. `local_at` es la hora de la captura en la Ciudad de México.
  - SQL: un solo SELECT, máximo 1,000 filas. Después de cargar las tablas, DuckDB no tiene acceso a archivos y su configuración queda bloqueada, así que no puede leer `api.env`.
- **Access log:** la unidad de la API corre uvicorn con `--no-access-log`, porque la URL de `/v1/plan` tiene las coordenadas del viaje.
- **Athena:** opcional, si hace falta SQL desde la consola de AWS.

## 6. Lugares nuevos para la búsqueda

Plan: el reporte semanal lista los lugares de Photon (`to.kind == "photon"`, con `osm`) elegidos en dos planes o más. Una persona revisa la lista, y `scripts/export_places.py` los agrega a `web/public/lugares.json`. Falta el reporte y falta la entrada de lugares extra en `export_places.py`.

## Puesta en marcha del registro de planes

Antes del merge, en el servidor de la API:

1. Agregar la declaración `WritePlans` de `deploy/api/iam-policy.json` al usuario IAM de la API.
2. Agregar `ECOBICI_PLAN_SINK=s3://<bucket>/plans` a `/etc/ecobici/api.env`.
3. Probar la rama con la unidad de systemd y comprobar que un plan llega a S3. Ver `deploy/api/README.md` y `AGENTS.md`.
