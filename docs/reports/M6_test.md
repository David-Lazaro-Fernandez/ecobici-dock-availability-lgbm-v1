# M6: prueba final en 2026-01 y 2026-09

Paso 8 de [`next_steps.md`](../next_steps.md). **Protocolo registrado el 2026-10-07, antes de leer cualquier etiqueta de los meses de prueba.** Los resultados se agregan abajo sin cambiar esta sección, cumplan o no.

## Protocolo

**Modelo.** El congelado en M6, sin ningún cambio:
- booster LightGBM entrenado en TRAIN, con parada temprana e isotónica global en VAL_FIT;
- Platt por subgrupo en saturadas + pico, reajustado cada semana con los 28 días anteriores, y Platt fijo de VAL_FIT si la ventana tiene < 5,000 filas (`p_lgbm_sub_roll`, `FROZEN`).

`ecobici.eval.test_report` reentrena (es determinista) y **compara byte por byte el booster, la isotónica y el Platt fijo con los artefactos congelados antes de calcular cualquier métrica**. Si algo difiere, se detiene. La lista de estaciones es la de M6: las que solo aparecen en los meses de prueba quedan fuera y se reporta cuántas son.

**Meses:**
- **2026-01, la prueba principal.** Mes completo, cadencia de ~15.5 min como en entrenamiento. Las ventanas semanales salen de VAL_REPORT (diciembre de 2025).
- **2026-09 desde el 11** (`splits.TEST_FROM`), **secundaria y reportada aparte.** Cadencia de 12 min: las etiquetas a 15 / 30 / 45 min se leen a 12 / 24 / 48 min, y su Brier absoluto no se compara con el de 2026-01 ([M2](M2_history.md#2026-09-en-detalle-2026-10-06)). No hay historia antes del 11, así que las primeras semanas usan el Platt fijo. Se reporta qué parte del subgrupo se calibró así.

**Comparación.** Las mismas líneas base, cortes, métricas y bootstrap por días (1,000 réplicas) de M6:
- **referencia fijada de antemano:** la mejor línea base ajustada con TRAIN en cada corte;
- **referencia justa:** la mejor de todas, incluidas `_tvf` e `_iso`.

**Criterios, para `p_lgbm_sub_roll` en 2026-01** (los mismos de M6):

| # | Criterio | Corte | Horizontes |
| --- | --- | --- | --- |
| 1 | BSS > 0 contra la referencia fijada de antemano | los 4 cortes | 15, 30, 45 |
| 2 | BSS ≥ 0.10 | saturadas + pico | 30 |
| 3 | Brecha de calibración ≤ 0.05 (bins con n ≥ 1,000) | saturadas + pico | 15, 30, 45 |

- **Cumple** si los tres criterios se cumplen en el valor puntual.
- **Cumple con holgura** si, además, con el IC 95 % por días, el límite inferior del BSS queda > 0 (≥ 0.10 en el criterio 2) y el superior de la brecha, ≤ 0.05.
- Un mes tiene ~1/3 de las filas de VAL_REPORT, así que menos bins llegan a n ≥ 1,000 y el criterio 3 juzga menos bins. **No se ajusta el umbral.** El diagrama de confiabilidad muestra todos los bins con su IC.

**2026-09** se evalúa con los mismos criterios, como evidencia adicional en temporada de lluvias. Si falla y 2026-01 cumple, se explica la diferencia (cadencia, Platt fijo, lluvia), pero no invalida el resultado.

**`p_lgbm`** (el modelo fijado antes de M6) se reporta al lado, como referencia.

**Después de correr:**
- Se corre **una sola vez**. No se cambia el modelo, los calibradores ni los criterios por lo que salga.
- Si no cumple, se documenta y la siguiente versión del modelo se juzga en la captura propia (paso 9), no en estos meses.
- Cualquier error de código que se encuentre después se corrige, y se reportan los dos resultados.

```sh
uv run python -m ecobici.eval.test_report
```

## Resultados

*Pendiente.*
