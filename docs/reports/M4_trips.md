# M4: Viajes de Ecobici

Fecha: 2026-10-06. Reproducible con:

```sh
uv run python -m ecobici.ingest.trips download   # ~5 GB de CSV → 956 MB de parquet
uv run python -m ecobici.ingest.trips quality
uv run python -m ecobici.eval.saturation --trips data/external/trips
```

## Ingesta

- **Origen:** las páginas de datos abiertos en inglés y en español. **2025-02 solo aparece en la de español.**
- **Cobertura:** 50 meses, de 2022-08 a 2026-09 (sistema nuevo, decisión del PRD), con **69.1 M de viajes**. Cuando un mes tiene varias subidas, se usa la más reciente.
- **Formato de los archivos:** se agrupan por **mes de llegada**. Hay 6 esquemas de nombre y 2 de columnas:
  - el habitual: `Ciclo_Estacion_Retiro`, `Fecha Arribo` / `Fecha_Arribo`…;
  - el de 2022-09: `CE_retiro`, BOM, año de 2 dígitos y horas sin cero inicial.
- **Normalización:** códigos de estación a 3 dígitos (`64` → `064`); se conservan las estaciones dobles (`390-391`); fechas en hora local de CDMX, con el fin del horario de verano del 2022-10-30 resuelto.
- **Privacidad:** **edad y género se descartan al leer.**
- **Descarga:** el servidor limita cada conexión a ~0.5 MB/s y se congela de vez en cuando. Por eso se usan 3 hilos, reintentos con espera creciente y reanudación con `Range`.

## Calidad

| | Resultado |
| --- | --- |
| Mapeo a estaciones del GBFS (origen y destino) | **≥ 99 % en todos los meses**; ≥ 99.9 % desde 2022-10. Solo falla el código `1000`, probablemente el taller o un depósito |
| Duración plausible (1–180 min) | ≥ 99.9 % desde 2022-10; 96.5 % en 2022-08 |
| Mediana de duración | 12–14 min |

**Problemas de la fuente, documentados y sin corregir:**

- **2022-09:** el 38.9 % de los viajes trae la hora como `MM:SS.f` (por ejemplo `55:30.0`); Excel perdió la hora. No se puede recuperar, así que esos viajes quedan con hora nula y se excluyen. El mes está fuera del periodo de entrenamiento.
- **2024-05:** la fuente solo publica del 1 al 15 de mayo (969 mil viajes). El flujo promedio divide entre los días presentes, así que no queda sesgado. También está fuera del periodo de entrenamiento.
- **Las estaciones dadas de baja** antes de hoy no se ligan, porque el mapeo usa el GBFS actual. Su efecto es menor al 1 % y solo en 2022.

✅ **Condición de salida de M4 cumplida:** más del 95 % de los viajes quedan ligados a una estación del GBFS.

## Variables para el modelo (`ecobici.features.trips`)

- **`net_flow`:** llegadas, salidas y flujo neto promedio por estación × franja de 15 min × tipo de día (entre semana o fin de semana).
- **`pair_duration`:** mediana y p75 de minutos por (origen, destino, hora de salida), con un mínimo de 5 viajes. Para pares con menos viajes se usa la estimación por distancia (RF9).
- **Ventana:** ambas reciben un rango de fechas explícito y **se ajustan solo con el periodo de entrenamiento**, para no filtrar información del futuro a validación y prueba.

## Saturación ponderada por demanda (pendiente de M3)

Cruzar cada viaje con el estado de su estación subestima la saturación: un viaje registrado prueba que **sí había lugar**. Por eso, la tasa de "llena" de cada estación × franja × tipo de día se pondera por la **demanda típica de llegadas** de esa franja.

| | Por tiempo | Por demanda (cota inferior) |
| --- | --- | --- |
| Todas las franjas | 2.7 % | 3.3 % |
| Entre semana, 08:30–10:30 | 4.1 % | **6.6 %** |

En el pico, al menos **1 de cada 15 llegadas** encuentra la estación llena. Concentrado en las ~100 estaciones saturadas del reporte M3, el problema que ataca el producto es mayor de lo que sugiere la tasa por tiempo. Esto refuerza el GO.
