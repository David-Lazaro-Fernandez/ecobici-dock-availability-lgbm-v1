# ¡Sí hay!

**¿Dónde dejo mi bici cuando llegue?** ¡Sí hay! te dice en qué estación de Ecobici (Ciudad de México) es más probable encontrar un anclaje libre, a la hora en que llegas.

<p align="center">
  <img src="docs/img/escritorio-plan.png" alt="Plan de viaje en escritorio: estación de salida, estación de llegada con 98 % de probabilidad y ruta en el mapa" width="860">
</p>

## El problema

Mucha gente deja la bici en la estación más cercana a su destino. A veces esa estación está llena. Entonces busca otra, y el tiempo de búsqueda puede ser mayor que el del viaje.

La app de Ecobici muestra los anclajes libres **ahora**. Tú llegas **dentro de 15, 30 o 45 minutos**.

## Qué hace

Escribes de dónde sales y a dónde vas. ¡Sí hay! responde:

- dónde tomar la bici, si tu estación de salida no tiene;
- en qué estación dejarla, con la probabilidad de encontrar lugar libre cuando llegues;
- otras estaciones de respaldo, ordenadas por tiempo, por distancia a pie o por disponibilidad;
- la ruta en el mapa, con las ciclovías de la ciudad.

<p align="center">
  <img src="docs/img/movil-plan.png" alt="Plan de viaje en el celular" width="280">
  &nbsp;&nbsp;
  <img src="docs/img/movil-busqueda.png" alt="Búsqueda por calle y número en el celular" width="280">
</p>

## Funciones

- **Probabilidad de lugar libre al llegar.** El porcentaje usa cuatro colores en el mapa, de menos de 50 % a 95 % o más.
- **Búsqueda por calle y número.** Escribe "Durango 49" o "Patricio Sanz 515". Si el número no está en los datos, la app lo estima y lo marca como "aprox.".
- **Lugares y estaciones.** También busca por nombre de lugar o de estación, y por tu ubicación.
- **Tres formas de ordenar.** Tiempo total, caminata al destino o disponibilidad.
- **Mapa con ciclovías.** Separadas, pintadas y compartidas.
- **Español e inglés.**
- **Tu opinión cuenta.** Después del viaje, la app pregunta si había lugar. Esas respuestas sirven para medir el modelo con datos reales.

<p align="center">
  <img src="docs/img/escritorio-busqueda.png" alt="Búsqueda de la dirección Durango 49 en escritorio" width="860">
</p>

## Cómo funciona

1. **Captura.** Cada 2 minutos guardamos el estado de todas las estaciones (feed público GBFS de Ecobici).
2. **Predicción.** Un modelo LightGBM calcula la probabilidad de que cada estación esté llena a los 15, 30 y 45 minutos. Usa el estado actual, la hora, el día y el clima.
3. **Recomendación.** Combina la probabilidad con la caminata y el tiempo en bici para elegir la mejor estación y las de respaldo.

## Qué tan bien funciona

En la prueba con datos de octubre a diciembre de 2025, el modelo reduce el error de la probabilidad cerca de 20 % frente a la mejor alternativa simple (suponer que la estación sigue como está). Las probabilidades también están calibradas: cuando dice "80 %", pasa cerca de 8 de cada 10 veces.

El detalle está en [`docs/modeling.md`](docs/modeling.md).

## Más información

| Tema | Documento |
| --- | --- |
| Qué construimos y por qué | [`docs/PRD.md`](docs/PRD.md) |
| Cómo se construyó y se probó el modelo | [`docs/modeling.md`](docs/modeling.md) |
| Plan de ingeniería y decisiones | [`docs/ENG_PLAN.md`](docs/ENG_PLAN.md) |
| Captura, predicción en vivo y evaluación | [`docs/ciclo_en_vivo.md`](docs/ciclo_en_vivo.md) |
| Instalar, probar y desarrollar | [`docs/desarrollo.md`](docs/desarrollo.md) |
| Reportes de cada etapa | [`docs/reports/`](docs/reports/) |

## Licencia

Apache 2.0. Los datos tienen sus propios términos: ver `docs/ENG_PLAN.md` §2.12.
