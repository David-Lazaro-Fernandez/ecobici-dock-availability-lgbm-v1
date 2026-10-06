# ecobici-dock-availability-lgbm-v1

ML model to predict whether you will end your ride and find parking at your destination dock (Ecobici, Mexico City).

- Product requirements: [`docs/PRD.md`](docs/PRD.md)
- Engineering plan, review findings and decisions: [`docs/ENG_PLAN.md`](docs/ENG_PLAN.md)
- How the model was built, justified and tested: [`docs/modeling.md`](docs/modeling.md)
- Stage reports (M2–M6): [`docs/reports/`](docs/reports/)

## Setup

Requires [uv](https://docs.astral.sh/uv/). On macOS, LightGBM also needs OpenMP:

```sh
brew install libomp
uv sync --all-extras
```

On the EC2 capture box only the collector is needed (no LightGBM, no OpenMP):

```sh
uv sync --extra collector --no-dev
```

## Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

## Dev station viewer

A Streamlit page to look at the live feed or local captures. It shows a map coloured by
label, a filterable table, and one station's docks and bikes over time.

```sh
uv run python -m ecobici.ingest.captures download   # optional: pull captures (bucket from S3_BUCKET_NAME)
uv run streamlit run apps/station_viewer.py --server.address localhost
```

## Layout

```
src/ecobici/
  config.py     # agreed constants (feed URLs, capture cadence, horizons, thresholds)
  collector/    # GBFS capture (runs on EC2, writes to S3)
  ingest/       # gbfs_raw, maxhalford, openmeteo, trips
  features/
  models/       # baselines, lgbm, calibration
  eval/         # metrics, temporal splits, recommendation simulator
  recommender/  # offline scoring
scripts/        # CLI entry point per stage
notebooks/      # V1–V6 diagnostics (read-only over data/)
tests/
docs/
```

`data/`, `raw/` and `artifacts/` are git-ignored: everything derived is rebuilt from raw captures.

## License

Apache 2.0. Data sources carry their own terms; see `docs/ENG_PLAN.md` §2.12.
