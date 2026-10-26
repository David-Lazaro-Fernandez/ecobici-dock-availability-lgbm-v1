# Desarrollo

Esta guía es para quien instala, prueba o cambia el código. Para entender el producto, lee el [`README`](../README.md).

## Instalar

Necesitas [uv](https://docs.astral.sh/uv/). En macOS, LightGBM también necesita OpenMP.

```sh
brew install libomp
uv sync --all-extras
```

En el servidor de captura (EC2) solo hace falta el colector, sin LightGBM ni OpenMP:

```sh
uv sync --extra collector --no-dev
```

## Revisiones

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

La app web tiene sus propias revisiones. Ejecuta todos los comandos de npm desde `web/`:

```sh
npm test
npm run build
npm run test:e2e
```

Las reglas de la app web están en [`web/AGENTS.md`](../web/AGENTS.md).

## Visor de estaciones

Una página de Streamlit para ver el feed en vivo o las capturas locales. Muestra un mapa coloreado por etiqueta, una tabla con filtros y los anclajes y bicis de una estación en el tiempo.

```sh
uv run python -m ecobici.ingest.captures download   # opcional: baja las capturas (bucket en S3_BUCKET_NAME)
uv run streamlit run apps/station_viewer.py --server.address localhost
```

## Capturas de pantalla del README

`web/scripts/screenshots.mjs` toma las capturas de `docs/img/` con la app real, la API en vivo y el mapa real. La API solo permite el origen de producción, por eso el script hace las llamadas desde Node.

```sh
cd web
NEXT_PUBLIC_API_URL=https://ecobici-docks.duckdns.org npm run build
python3 -m http.server 3200 --directory out &
node scripts/screenshots.mjs ../docs/img
```

## Estructura del repositorio

```text
src/ecobici/
  config.py     constantes acordadas (URL de los feeds, cadencia de captura, horizontes, umbrales)
  collector/    captura GBFS (corre en EC2, escribe en S3)
  ingest/       gbfs_raw, maxhalford, openmeteo, trips
  features/
  models/       líneas base, lgbm, calibración
  eval/         métricas, cortes temporales, simulador de recomendaciones
  recommender/  puntuación offline y plan
  api.py        API HTTP (FastAPI)
web/            app web (Next.js)
deploy/         servidores: API (OCI) y captura (EC2)
apps/           visor de estaciones
scripts/        un comando por etapa
notebooks/      diagnósticos V1–V6 (solo leen data/)
tests/
docs/
```

`data/`, `raw/` y `artifacts/` no están en git. Todo lo derivado se reconstruye desde las capturas crudas.

## Despliegue y ciclo en vivo

- API: [`deploy/api/README.md`](../deploy/api/README.md). Un merge a `main` es un deploy.
- Captura: `deploy/ec2/`.
- Mapa del ciclo en vivo: [`ciclo_en_vivo.md`](ciclo_en_vivo.md).
