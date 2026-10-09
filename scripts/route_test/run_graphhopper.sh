#!/usr/bin/env bash
# Start GraphHopper with the bike_fast and bike_lanes profiles on a Mexico City map.
#
#   scripts/route_test/run_graphhopper.sh    # from the repo root; needs Docker and uv
#
# Steps: download the Geofabrik Mexico extract, clip the Ecobici area, tag the bike lanes,
# then run GraphHopper in Docker with 1 CPU, as on the API server. A step with output is skipped.
# The server listens on 127.0.0.1:8989. Stop it with `docker rm -f gh-route-test`.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CONF="$ROOT/scripts/route_test"
DATA="$ROOT/data/route_test"
GH_VERSION=11.0
GH_JAR="$DATA/graphhopper-web-$GH_VERSION.jar"
MEXICO_URL=https://download.geofabrik.de/north-america/mexico-latest.osm.pbf
# West, south, east, north: the Ecobici stations plus ~4 km.
BOX=-99.26,19.30,-99.09,19.51
CONTAINER=gh-route-test

mkdir -p "$DATA"

if [ ! -f "$GH_JAR" ]; then
  curl -fsSL -o "$GH_JAR" \
    "https://github.com/graphhopper/graphhopper/releases/download/$GH_VERSION/graphhopper-web-$GH_VERSION.jar"
fi

if [ ! -f "$DATA/cdmx.osm.pbf" ]; then
  curl -fsSL -o "$DATA/mexico.osm.pbf" "$MEXICO_URL"
  expected="$(curl -fsSL "$MEXICO_URL.md5" | cut -d' ' -f1)"
  actual="$(md5 -q "$DATA/mexico.osm.pbf" 2>/dev/null || md5sum "$DATA/mexico.osm.pbf" | cut -d' ' -f1)"
  if [ "$expected" != "$actual" ]; then
    echo "Checksum mismatch for mexico.osm.pbf" >&2
    exit 1
  fi
  docker run --rm -v "$DATA:/data" debian:12-slim bash -c \
    "apt-get update -qq >/dev/null && apt-get install -y -qq osmium-tool >/dev/null 2>&1 &&
     osmium extract --strategy=smart -b $BOX /data/mexico.osm.pbf -o /data/cdmx.osm.pbf --overwrite"
  rm "$DATA/mexico.osm.pbf"
fi

if [ ! -f "$DATA/cdmx_lanes.osm.pbf" ]; then
  uv run --with osmium python "$CONF/tag_lanes.py" "$DATA/cdmx.osm.pbf" "$DATA/cdmx_lanes.osm.pbf"
  rm -rf "$DATA/graph-cache"
fi

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker run -d --name "$CONTAINER" --cpus=1 --memory=2g \
  -p 127.0.0.1:8989:8989 -p 127.0.0.1:8990:8990 \
  -v "$CONF:/gh/conf:ro" -v "$DATA:/gh/data" \
  eclipse-temurin:21-jre \
  java -Xmx1500m -jar "/gh/data/graphhopper-web-$GH_VERSION.jar" server /gh/conf/config.yml >/dev/null

started=$(date +%s)
until curl -fs -m 2 http://127.0.0.1:8990/healthcheck >/dev/null 2>&1; do
  if [ "$(docker inspect -f '{{.State.Running}}' "$CONTAINER")" != "true" ]; then
    docker logs "$CONTAINER" 2>&1 | tail -20 >&2
    exit 1
  fi
  sleep 2
done
echo "GraphHopper ready after $(( $(date +%s) - started )) s on http://127.0.0.1:8989"
