# Siguientes pasos: del modelo M6 a la prueba final

Estado al 2026-10-06. Resume la revisión de [`modeling.md`](modeling.md) y lo que se decidió después de revisar la captura propia. Los plazos y las etapas generales siguen en [`ENG_PLAN.md`](ENG_PLAN.md).

## Dónde estamos

- **M6:** en VAL_REPORT (2025-10 → 2025-12), LightGBM reduce el Brier ~20 % frente a la mejor línea base en todos los cortes y horizontes (BSS +0.17 … +0.22). La calibración dentro de saturadas + pico solo cumple la meta a 30 min (15 min: 0.059, 30 min: 0.047, 45 min: 0.073; meta ≤ 0.05).
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

1. **Mismas condiciones para líneas base y modelo.** Hoy las líneas base se ajustan solo con TRAIN, y la calibración del modelo usa VAL_FIT (2025-08, 2025-09), más reciente. Reajustar `p_persist_cal` y `p_hist` con TRAIN + VAL_FIT, o calibrarlas en VAL_FIT, y recalcular el BSS. Así se sabe cuánto del ~20 % viene del modelo y no de usar datos más recientes.
2. **Intervalos de confianza.** Bootstrap por bloques de días, idealmente estación × día, con IC 95 % para el BSS y la brecha de calibración. Dice si 0.047 contra 0.059 es una diferencia real o ruido. Agregar también log loss del modelo y diagramas de confiabilidad.
3. **Calibración por subgrupo (saturadas + pico).** Ajustarla en VAL_FIT, revisarla en VAL_REPORT y congelarla. **No elegir el calibrador mirando TEST.**
4. **Septiembre de 2026.** M2 lo marca ❌ (72 huecos de más de 1 h). Decidir si se filtran los huecos o se excluye el mes. Reportarlo separado de 2026-01.
5. **Pipeline de evaluación sobre la captura.** GBFS JSON → las mismas 33 variables → predicciones → métricas. Probarlo solo en la ventana del 2026-10-06, 11:37–14:38 hora local (17:37–20:38 UTC). Esa ventana queda marcada como *dev* y fuera de la prueba final para siempre.

### Mientras corre la captura (2–4 semanas)

6. **Revisar la salud de la captura cada pocos días** (ver [Cómo sincronizar](#cómo-sincronizar-la-captura)). Un hueco como el del primer día (105 min) no debe repetirse en las mañanas entre semana.
7. *(Opcional)* Agregar `botocore[crt]` al extra `collector`, desde PyPI, para no tener que exportar credenciales.

### Después, una sola vez

8. **Prueba final de 15, 30 y 45 min:** congelar el modelo y evaluarlo en 2026-01 y 2026-09. Se puede hacer apenas terminen los pasos 1–4.
9. **Prueba en datos reales:** el mismo modelo congelado sobre la captura propia, con al menos ~10 mañanas entre semana (~2 semanas). Los intervalos del paso 2 dicen si alcanza o hace falta más.
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
