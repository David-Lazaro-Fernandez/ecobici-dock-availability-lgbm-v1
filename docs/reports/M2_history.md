# M2 — Diagnóstico del histórico externo (V4)

Fecha: 2026-10-06. Reproducible con:

```sh
uv run python -m ecobici.ingest.maxhalford download
uv run python -m ecobici.ingest.maxhalford diagnose
uv run python -m ecobici.ingest.openmeteo
```

## MaxHalford, CDMX

27 archivos mensuales (84 MB) con un snapshot completo de ~677 estaciones por commit. **Tiempo cubierto** es la fracción del mes en tramos donde la siguiente lectura llega en ≤ 30 min. Conteo de franjas de 15 min con datos no sirve aquí: la cadencia sana (~15.5 min) mide casi lo mismo que una franja, así que incluso un mes completo deja franjas vacías.

| Month | Snapshots | Median gap (min) | p95 gap | Gaps >1 h | Max gap (h) | Covered days | Time covered | Healthy |
|---|---|---|---|---|---|---|---|---|
| 2024-04 | 158 | 15.0 | 22.5 | 0 | 0.6 | 1.6 | 5.4% | ❌ |
| 2024-08 | 851 | 15.1 | 21.8 | 1 | 3168.0 | 8.7 | 28.0% | ❌ |
| 2024-09 | 2691 | 15.3 | 24.6 | 0 | 0.8 | 27.5 | 91.8% | ✅ |
| 2024-10 | 2767 | 15.3 | 25.4 | 0 | 0.9 | 28.3 | 91.4% | ✅ |
| 2024-11 | 2658 | 15.5 | 25.1 | 0 | 0.8 | 27.2 | 90.5% | ✅ |
| 2024-12 | 2735 | 15.4 | 25.3 | 0 | 0.8 | 27.8 | 89.8% | ✅ |
| 2025-01 | 2757 | 15.4 | 25.1 | 2 | 1.7 | 28.2 | 91.0% | ✅ |
| 2025-02 | 2510 | 15.3 | 24.7 | 0 | 0.7 | 25.7 | 91.8% | ✅ |
| 2025-03 | 2736 | 15.6 | 24.9 | 0 | 0.8 | 28.0 | 90.4% | ✅ |
| 2025-04 | 2600 | 15.6 | 28.1 | 2 | 1.3 | 26.4 | 87.9% | ✅ |
| 2025-05 | 2653 | 15.5 | 32.0 | 1 | 4.8 | 26.7 | 86.2% | ✅ |
| 2025-06 | 2546 | 15.6 | 34.5 | 1 | 1.0 | 25.6 | 85.3% | ✅ |
| 2025-07 | 1193 | 20.8 | 46.1 | 29 | 278.8 | 12.1 | 39.1% | ❌ |
| 2025-08 | 2613 | 15.6 | 36.4 | 0 | 1.0 | 26.6 | 85.7% | ✅ |
| 2025-09 | 2612 | 15.7 | 26.7 | 1 | 4.5 | 26.7 | 89.1% | ✅ |
| 2025-10 | 2696 | 15.8 | 27.6 | 0 | 0.8 | 27.6 | 88.9% | ✅ |
| 2025-11 | 2559 | 15.8 | 34.1 | 2 | 1.4 | 26.0 | 86.5% | ✅ |
| 2025-12 | 2592 | 15.7 | 37.8 | 0 | 0.9 | 26.2 | 84.6% | ✅ |
| 2026-01 | 2441 | 15.9 | 39.3 | 3 | 1.1 | 25.3 | 81.7% | ✅ |
| 2026-02 | 1593 | 24.2 | 47.7 | 32 | 4.3 | 16.2 | 57.8% | ❌ |
| 2026-03 | 1742 | 24.4 | 49.1 | 39 | 2.1 | 17.5 | 56.5% | ❌ |
| 2026-04 | 1260 | 30.3 | 61.8 | 91 | 1.4 | 10.2 | 34.2% | ❌ |
| 2026-05 | 927 | 42.6 | 84.8 | 241 | 3.9 | 3.8 | 12.2% | ❌ |
| 2026-06 | 702 | 55.8 | 110.7 | 310 | 2.4 | 1.0 | 3.3% | ❌ |
| 2026-07 | 426 | 89.7 | 211.2 | 375 | 4.5 | 0.0 | 0.1% | ❌ |
| 2026-08 | 730 | 42.9 | 155.4 | 204 | 11.2 | 2.9 | 9.2% | ❌ |
| 2026-09 | 2417 | 12.0 | 14.4 | 72 | 7.4 | 19.7 | 65.5% | ❌ |

Covered time, all months: 524 days
Healthy months (>= 80% covered): 16, 430 covered days

### Conclusiones

- **Periodo útil: de 2024-09 a 2026-01** (16 meses sanos, 430 días cubiertos). Solo falla 2025-07 (12 días cubiertos). Es un año completo, con la temporada de lluvias de 2024 y de 2025.
- **De 2026-02 a 2026-08 el scraper se degradó** (mediana de 24 a 90 min entre lecturas). Esos meses no sirven para horizontes de 15 min. Septiembre de 2026 se recuperó (12 min), pero tiene 72 huecos de más de 1 h.
- **Cadencia de ~15.5 min.** Confirma los horizontes de 15/30/45 min para MaxHalford y 10/20 min solo con la captura propia (decisión 4).
- **El filtro es por ejemplo, no por mes.** Un ejemplo (estación, *t*, *h*) entra si hay lectura a ≤ 7.5 min de *t* y a ≤ 7.5 min de *t + h*. Así los meses parciales aportan sus tramos buenos.
- **Sin `last_reported`.** En MaxHalford no se puede aplicar la regla de `stale`. Las lecturas se toman como válidas al momento del commit, y la diferencia se mide contra la captura propia en M7.

### Separación temporal propuesta para M5/M6

| Bloque | Meses | Uso |
| --- | --- | --- |
| Entrenamiento | 2024-09 → 2025-06 | Ajuste |
| Validación | 2025-08 → 2025-12 | Hiperparámetros, calibración, metas numéricas |
| Prueba | 2026-01 y 2026-09 | Nunca vistos hasta el final |
| Prueba final | Captura propia (oct–nov 2026) | M7 |

Se dejan 2025-07 y de 2026-02 a 2026-08 fuera de todos los bloques.

## Open-Meteo (pronóstico histórico)

- Punto: (19.41, −99.17). El centroide real de las estaciones es (19.408, −99.168), y el área de servicio mide unos 14 × 9 km, del tamaño de una celda del modelo.
- Del 2024-04-01 al 2026-10-05: 22,032 horas, **sin valores faltantes** en `temperature_2m` ni en `precipitation`.
- Las horas con lluvia (≥ 0.1 mm) se concentran de junio a octubre (165–365 h/mes) contra 9–68 h/mes en la temporada seca: el patrón esperado.
- V5 queda sin efecto: se usa la misma fuente para entrenar y para predecir (decisión 2).

## Condición de salida de M2

✅ Se sabe qué periodo del histórico sirve para entrenar a 15 min, y la fuente de clima está decidida y descargada.
