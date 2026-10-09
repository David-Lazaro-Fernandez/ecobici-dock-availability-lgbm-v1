# Rutas por ciclovía con GraphHopper: prueba en laptop

Fecha: 2026-10-08. Reproducible con los scripts de `scripts/route_test/` (ver "Cómo correrla"). Datos de salida en
`data/route_test/`.

## Por qué

Algunas personas usuarias piden la ruta que pase más por ciclovías, no la más rápida. El OSRM público que dibuja las
rutas hoy tiene un perfil fijo: no permite preferir ciclovías y no dice qué parte de la ruta va por una. Esta prueba
mide si un GraphHopper propio puede dar ese modo, cuánto cuesta en minutos y si cabe en el servidor de la API
(1 CPU, 6 GB).

El ranking del planificador no cambia: sigue con la duración real de los viajes Ecobici. GraphHopper solo agregaría
la ruta por ciclovías, su porcentaje en ciclovía y los minutos extra.

## Montaje

- GraphHopper 11.0 en Docker, limitado a 1 CPU y 2 GB, con un recorte de la Ciudad de México del extracto de
  Geofabrik (12 MB).
- Dos perfiles con preparación CH:
  - `bike_fast`: el modelo `bike.json` de GraphHopper, sin cambios.
  - `bike_lanes`: el mismo modelo más `scripts/route_test/lanes.json`. Las calles sin ciclovía cuentan como más
    largas: 1.0 separada, 0.8 pintada, 0.6 compartida o residencial, 0.5 de servicio, 0.2 avenida sin carril. Los
    minutos reportados siguen siendo reales.
- Clases de ciclovía: `src/ecobici/bike_lanes.py`. En el recorte hay 3,179 tramos: 1,857 separados, 291 pintados y
  1,031 compartidos.

### La marca de ciclovía

GraphHopper no tiene un valor para "carril pintado". Su `bike_priority` no sirve: da 1.2 a una calle residencial sin
carril y 1.1 a una calle con carril pintado. Por eso `tag_lanes.py` agrega al mapa una relación `route=mtb` por cada
tramo de ciclovía, y el valor `mtb_network` lleva la clase (icn separada, ncn pintada, rcn compartida). Ningún perfil
de bici lee `mtb_network`.

Revisión en 100 rutas al azar, con el prototipo de los scripts (mismas reglas, mismos 3,179 tramos):

- `bike_fast` da la misma ruta con y sin la marca (100 de 100).
- `mtb_network` coincide con la clase de `bike_lanes.py` en todos los puntos de las rutas.

## Resultados

Muestra: 400 pares de estaciones al azar (semilla fija) con al menos 20 viajes reales cada uno, 46,640 viajes en
total. Viaje real mediano: 14.9 min; distancia en línea recta mediana: 2.2 km.

### Tiempo contra los viajes reales

| Motor | Error absoluto mediano | Motor / real | Error tras una corrección de velocidad | Correlación |
| --- | --- | --- | --- | --- |
| OSRM público | 2.4 min | 0.84 | 1.3 min | 0.921 |
| GraphHopper `bike_fast` | 5.0 min | 0.66 | 1.4 min | 0.920 |

- GraphHopper supone ciclistas más rápidos: sus tiempos son 34 % más cortos que los reales.
- Con un solo factor de velocidad, los dos motores quedan casi iguales. El factor se ajustó con los mismos 400 pares,
  así que el resultado es un poco optimista.
- Las rutas de GraphHopper son un poco más largas: 2.93 km contra 2.78 km de mediana.

### `bike_lanes` contra `bike_fast`

Porcentaje en ciclovía = separada + pintada. Las compartidas no cuentan.

- Porcentaje en ciclovía: de 38 % a 61 % en promedio (mediana: de 37 % a 69 %). Separada: de 33 % a 51 %.
- Minutos extra (minutos de GraphHopper): mediana 0.7, p75 2.1, p90 4.1, máximo 11.2. En minutos reales son cerca de
  1.5 veces más, por el factor de velocidad.
- 26 % de los pares no cambia: la ruta rápida ya va por ciclovía.
- 45 % de los pares gana 20 puntos o más, con una mediana de 1.6 min extra.
- 7 % de los pares sale más de 50 % más largo. Para ellos, el planificador debe usar la ruta rápida.

| Distancia en línea recta | Pares | Porcentaje en ciclovía | Minutos extra (mediana) |
| --- | --- | --- | --- |
| 0–2 km | 172 | 28 % → 48 % | 0.4 |
| 2–4 km | 177 | 43 % → 69 % | 0.9 |
| 4–7 km | 49 | 56 % → 76 % | 2.0 |

### Recursos (laptop, no el servidor)

- Arranque: 14 s con importación del mapa y preparación de los dos perfiles. Grafo: 27 MB.
- Memoria del contenedor: 350 MiB al arrancar, 505 MiB después de la prueba de carga.
- Carga con 1 CPU (`load_test.py`, rutas al azar de los dos perfiles):

| Clientes a la vez | Rutas/s | p50 | p95 |
| --- | --- | --- | --- |
| 1 | 796 | 1.2 ms | 1.6 ms |
| 4 | 1,246 | 1.6 ms | 3.5 ms |
| 16 | 928 | 4.2 ms | 81.9 ms |
| 32 | 632 | 75.9 ms | 103.2 ms |

Los clientes corren en la misma Mac, fuera del contenedor. La medida no incluye la API, que en el servidor comparte el
mismo CPU, y el CPU de la Mac no es el del servidor OCI.

## Lo que falta

- **Revisión por personas:** alguien que use la bici en la Ciudad de México revisa unas 20 rutas comunes en el mapa.
- **Ajuste de penalizaciones:** los valores de `lanes.json` son una primera propuesta.
- **Cobertura de OSM:** comparar las ciclovías de OSM con el mapa oficial de la ciudad.
- **Pendientes:** el perfil no usa elevación.
- **Servidor:** no se probó en el servidor OCI.
- **Nombre:** en la app, "Más ciclovía", no "la más segura". Un carril pintado no es una ciclovía separada, y OSM no
  tiene todas las ciclovías.
- **Estaciones con coordenadas erróneas:** 9 estaciones del bundle quedan fuera de la prueba: 5 en Montreal (sid 2, 3,
  4, 13, 54) y 4 en 0,0 (sid 711, 714, 718, 719).

## Cómo correrla

Desde la raíz del repo, con Docker y el bundle de `artifacts/serving/`:

```sh
scripts/route_test/run_graphhopper.sh              # descarga, recorte, marca de ciclovías, servidor en :8989
uv run python scripts/route_test/load_test.py      # ~1 min
uv run python scripts/route_test/route_pairs.py    # ~11 min, 1 petición/s al OSRM público
uv run python scripts/route_test/analyze.py
docker rm -f gh-route-test
```

`run_graphhopper.sh` salta un paso si su salida ya existe. Para empezar de cero, borra `data/route_test/`.
