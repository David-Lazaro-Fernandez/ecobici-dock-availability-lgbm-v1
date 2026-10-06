# PRD: Recomendador de estación destino Ecobici CDMX

Oct 6, 2026 · @Dave

## Resumen y problema

Este producto recomienda, dado un origen, un destino y una hora de salida, la cicloestación de Ecobici donde es más probable encontrar anclaje libre al llegar y que minimiza el tiempo total del viaje, incluido el que se pierde buscando lugar.

Hoy las personas suelen dirigirse a la estación más cercana a su trabajo o destino y, con frecuencia, la encuentran llena. Entonces buscan la siguiente, que también puede estar llena, y el tiempo de búsqueda llega a superar al del viaje mismo. La app oficial de Ecobici permite ver la disponibilidad de las estaciones en tiempo real ([App Store](https://apps.apple.com/us/app/ecobici/id1608397837)), pero ese dato describe el presente de la estación, no cómo estará dentro de 15 o 20 minutos, cuando la persona llegue.

La propuesta es sustituir "¿cuántos anclajes hay ahora?" por "¿qué probabilidad hay de encontrar anclaje cuando yo llegue?", y combinarla con la distancia a pie al destino para elegir la mejor opción y una alternativa de respaldo.

**Hipótesis por validar.** El PRD parte de que las estaciones cercanas a destinos frecuentes se llenan con frecuencia y de que buscar lugar llega a costar más tiempo que el viaje. Ambas cosas vienen de la experiencia de uso, no de datos medidos; la validación V1 las comprueba con la captura propia antes de construir el recomendador.

## Objetivos, no objetivos y métricas de éxito

La primera fase tiene éxito si el modelo estima la probabilidad de anclaje libre mejor que las alternativas simples y con probabilidades que se puedan creer; las recomendaciones se evalúan después por simulación sobre datos históricos.

**Objetivos**

Recomendar la estación con menor tiempo total esperado hacia el destino.

Estimar la probabilidad de anclaje libre al llegar, con una calibración confiable.

Ofrecer una estación de respaldo cuya probabilidad de estar llena dependa poco de la principal.

**No objetivos de la primera fase**

Rebalanceo operativo de bicicletas (es tarea del operador).

Planeación de rutas ciclistas.

Seguridad del entorno como criterio de recomendación (fase 2).

Predecir si habrá bicis para tomar en la estación de salida.

API e interfaz de usuario (mapa web o app): se construyen en una fase posterior, cuando el modelo funcione.

**Métricas**

| Métrica | Qué mide | Meta |
| --- | --- | --- |
| Brier score | Calidad de la probabilidad de estación llena | Mejor que ambas líneas base |
| Calibración | Si "80 %" se cumple unas 8 de cada 10 veces | Curva cercana a la diagonal |
| Recomendación exitosa | Porcentaje de veces que la estación sugerida sí tenía anclaje al llegar (simulación sobre estados históricos) | Mayor que "la más cercana al destino" |
| Tiempo extra de búsqueda | Minutos adicionales por no encontrar lugar; se estima por simulación, no hay dato observado | Menor que la línea base |
| Desempeño por tipo de estación | Centro frente a periferia | Sin brechas grandes |

Las metas numéricas se fijan después de medir las líneas base; hoy no existe un valor de referencia.

## Usuarios y escenarios de uso

El usuario principal es quien viaja en Ecobici a un destino fijo, sobre todo al trabajo. La encuesta Ecobici de 2017, citada en un [estudio de simulación del inventario](https://www.sciencedirect.com/science/article/abs/pii/S2213624X21000791), reporta que 68 % de los usuarios usa la bicicleta para ir o volver de casa o del trabajo. Que las estaciones cercanas al destino se saturen en hora pico es una hipótesis que este PRD propone validar (ver Validaciones y criterios de decisión).

**Viaje al trabajo en hora pico.** La persona sale de una estación, indica su destino y recibe la mejor estación para dejar la bici, con su probabilidad de tener lugar y un respaldo.

**Viaje en curso.** Mientras pedalea, el estado de las estaciones cambia; la recomendación se recalcula con datos en vivo y avisa si conviene desviarse, con un aviso mínimo o por voz para no usar el teléfono mientras se pedalea.

**Análisis de patrones (secundario).** Quien analiza el sistema identifica estaciones que se llenan o vacían de forma crónica y a qué horas.

## Alcance por fases y requisitos funcionales

El MVP es primero un modelo, sin API: captura de datos y estimación de la probabilidad de anclaje libre por estación. Cuando el modelo funcione, el recomendador (para un mapa web o una app, mediante una API en una fase posterior) recibe origen, destino y hora de salida, y devuelve una estación recomendada y un respaldo, cada una con su probabilidad de anclaje libre y su tiempo total esperado.

| # | Requisito | Detalle |
| --- | --- | --- |
| RF1 | Entrada | Estación o coordenadas de origen, coordenadas de destino y hora de salida |
| RF2 | Estaciones candidatas | Las que estén a 500 m o menos a pie del destino |
| RF3 | Probabilidad por candidata | P(hay anclaje libre) al momento estimado de llegada: salida más tiempo en bici hasta esa estación |
| RF4 | Puntaje | Tiempo esperado = tiempo en bici + caminata al destino + (1 − p) × costo de falla; el costo de falla arranca como constante (5 a 10 min, supuesto) |
| RF5 | Salida | Mejor estación, respaldo, probabilidad de cada una y tiempo esperado |
| RF6 | Respaldo | Elegido por baja dependencia con la principal, estimada como P(respaldo llena \| principal llena) con el histórico |
| RF7 | Exclusiones | Estaciones fuera de servicio o con devolución deshabilitada, y anclajes deshabilitados |
| RF8 | Recalcular en ruta | Actualizar la recomendación con el feed en vivo (después del primer prototipo) |
| RF9 | Tiempos de viaje | Tiempo en bici y caminata estimados por distancia con velocidades supuestas; los viajes históricos por par de estaciones ajustan el tiempo en bici cuando existan datos |

## Ejemplo del recomendador

Un ejemplo con cuatro estaciones candidatas muestra por qué no basta con ordenar por probabilidad.

&#91;embedded content: esquema de trabajo · salida, 4 estaciones candidatas y destino\]

Cada número es la probabilidad de encontrar anclaje libre en esa estación al llegar (supuesto por confirmar). En el esquema original el destino no estaba conectado a ninguna estación; en el MVP, la distancia a pie de cada estación al destino también entra al puntaje (RF4), así que la mejor opción no es necesariamente la de mayor probabilidad.

## Fase posterior: requisitos de la API, privacidad y licencias

Esta sección se deja como referencia para una fase posterior, cuando exista un modelo; las licencias, en cambio, aplican desde ahora a los datos de entrenamiento. La API debe responder con una recomendación útil aunque falten datos, y no debe guardar información que identifique a quien consulta. Lo marcado como propuesta aún no está decidido.

| Aspecto | Propuesta | Estado |
| --- | --- | --- |
| Consulta | Entrada: origen, destino y hora de salida (por defecto, ahora). Respuesta: estación recomendada, respaldo, probabilidad de anclaje libre y tiempo total esperado de cada una, y la hora de los datos usados | Propuesta |
| Datos en vivo | Lee el estado actual del feed GBFS con una caché corta; el tiempo de vida del feed (unos 10 s según un proyecto de terceros) no está verificado | Por verificar |
| Si el feed falla | Responder con aviso y usar el promedio histórico por estación y franja, marcando la respuesta como de baja confianza | Propuesta |
| Tiempos de viaje | Tiempo en bici y caminata estimados por distancia con velocidades supuestas; los viajes históricos por par de estaciones ajustan el tiempo en bici cuando existan datos. Sin servicio de rutas en el MVP | Propuesta; velocidades por definir |
| Latencia, autenticación y límites | Latencia objetivo, forma de autenticación y límites de uso por cliente | Por definir |
| Avisos en ruta | Mínimos o por voz, sin requerir que la persona use el teléfono mientras pedalea | Propuesta |

**Privacidad**

Origen y destino son datos personales: no asociarlos a identificadores de usuario. Si se guardan para mejorar el modelo, se agregan y se define cuánto tiempo se conservan (por definir).

Propuesta: no usar edad ni género del usuario, que vienen en los viajes históricos, como variables del modelo ni de la API.

**Licencias y términos de uso**

Proyecto: Apache 2.0 (decidido).

Feed GBFS: términos de uso sin verificar; revisar el campo de licencia del propio feed.

Open-Meteo: datos CC BY 4.0, con atribución; el acceso gratuito es solo para uso no comercial, así que un producto comercial necesitaría un plan de pago u otra fuente.

MaxHalford/bike-sharing-history: licencia y términos por revisar en el repositorio.

Datos del portal de datos abiertos de la Ciudad de México: CC BY 4.0 según el portal, con atribución.

## Datos y fuentes

El insumo crítico es el estado de cada estación a lo largo del tiempo, y Ecobici no publica ese histórico: hay que construirlo capturando el feed en vivo y complementarlo con capturas comunitarias.

| Fuente | Uso en el modelo | Estado de verificación |
| --- | --- | --- |
| [Feed GBFS de Ecobici](https://gbfs.mex.lyftbikes.com/gbfs/gbfs.json) | Estado actual por estación y variable objetivo | La URL aparece en la página oficial; versión, campos y licencia sin verificar |
| Colector propio del feed | Histórico de disponibilidad | Por construir: captura continua cada 1 a 5 minutos (frecuencia por definir); primero 3 días para validar el flujo y luego 1 mes de captura, con reentrenamiento diario |
| [MaxHalford/bike-sharing-history](https://github.com/MaxHalford/bike-sharing-history) | Histórico de disponibilidad y de clima para entrenar | Repositorio verificado; inicio, frecuencia y huecos de Ciudad de México sin medir |
| [Viajes mensuales de Ecobici](https://ecobici.cdmx.gob.mx/en/open-data/) | Flujo neto por estación y franja, duración de viaje | Verificado, de 2010-02 a 2026-09; nombres de archivo inconsistentes; solo registra demanda satisfecha |
| [Cicloestaciones (nuevo sistema)](https://datos.cdmx.gob.mx/dataset/cicloestaciones-ecobici-nuevo-sistema) | Ubicación de estaciones | Verificado, corte del 17/10/2024; la capacidad vigente debe salir del GBFS |
| [Open-Meteo](https://open-meteo.com/) | Clima actual (lluvia y temperatura) al momento de predecir | Elegida para el clima actual: sin clave y con datos CC BY 4.0, pero el acceso gratuito es para uso no comercial; resolución de 9 a 25 km, no es una estación local |

Los enlaces y el estado de verificación de cada fuente están en la sección Fuentes consultadas, al final.

## Modelo y evaluación

El modelo base es un clasificador de gradient boosting (LightGBM) que estima la probabilidad de que una estación esté llena en el momento de la llegada, y se valida siempre con una separación temporal.

**Variable objetivo.** La estación i está "llena" en t\_llegada si no tiene anclaje utilizable, con t\_llegada = salida + duración estimada del viaje. Conviene entrenar varios horizontes (por ejemplo 10, 20 y 30 minutos) y distinguir "llena" de "fuera de servicio" para no confundir saturación con fallas.

**Variables de entrada**

Ocupación actual y rezagos recientes de la estación.

Ocupación de estaciones vecinas (a unos 300 m).

Flujo neto histórico por estación y franja horaria, calculado con los viajes.

Hora, día de la semana, feriados, lluvia y temperatura (del histórico de MaxHalford al entrenar y de Open-Meteo al predecir; hay que comprobar que ambas fuentes sean comparables).

Capacidad, anclajes deshabilitados y antigüedad de la estación.

Duración del viaje: distribución por par de estaciones y hora (mediana con margen de seguridad).

**Líneas base obligatorias**

Persistencia: la estación seguirá como está ahora.

Promedio histórico por estación y franja de 15 minutos.

Si el modelo no supera ambas con claridad, no se justifica su complejidad. Las redes de grafos espaciotemporales se prueban solo si el modelo tabular se estanca.

**Validación.** Entrenar con semanas anteriores y evaluar con semanas posteriores, nunca con una mezcla aleatoria. Aunque se reentrene a diario, se conserva un bloque final de días que el modelo no vio. Con 1 mes de captura propia habrá pocos fines de semana y casi ninguna variación estacional, por lo que el histórico externo se usa para cubrir esa carencia una vez medida su cobertura.

## Fase 2: seguridad del entorno

La seguridad entra como criterio adicional solo después de que la fase 1 supere sus líneas base, porque los datos de delitos son más débiles que los de uso.

**Delitos.** Las [carpetas de investigación de la FGJ](https://datos.cdmx.gob.mx/dataset/carpetas-de-investigacion-fgj-de-la-ciudad-de-mexico) traen fecha, hora, tipo de delito y coordenadas desde 2016. Se cuentan en buffers de 100, 200 y 300 m alrededor de cada estación, normalizados por exposición y con análisis de sensibilidad.

**Limitaciones.** Subregistro, georreferencia aproximada y sesgo hacia zonas con más denuncia. Además, un estudio del ITAM ([Cymet Monroy y Larreguy, 2026](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6132346)) estima que abrir una estación reduce el delito reportado en unos 2.3 incidentes al mes, así que el delito histórico no es independiente de la presencia de la estación.

**Cámaras C5.** La [capa de postes con WiFi](https://datos.cdmx.gob.mx/dataset/ubicacion-acceso-gratuito-internet-wifi-c5) es de 2021 y cubre solo parte de las cámaras; sirve como piso mínimo de vigilancia, no como inventario. El inventario completo requeriría una solicitud de transparencia.

**Uso en el producto.** Como desempate entre estaciones con disponibilidad similar ("misma probabilidad de lugar, entorno con menos incidentes"), nunca como sustituto de la probabilidad de anclaje.

## Riesgos, supuestos y limitaciones

El mayor riesgo es no tener suficiente histórico de disponibilidad para entrenar y evaluar con honestidad.

| Riesgo | Efecto | Mitigación |
| --- | --- | --- |
| Histórico insuficiente o con huecos | Métricas optimistas, sin estacionalidad | Medir la cobertura del histórico externo antes de depender de él; seguir capturando |
| Los viajes solo registran demanda satisfecha | Subestima la saturación | No usar viajes como única fuente de la variable objetivo |
| Anclajes deshabilitados o estación fuera de servicio | Se confunde falla con estar llena | Guardar el JSON crudo y separar los estados |
| Cambios del sistema (expansión, nuevas estaciones) | Patrones que dejan de valer | Entrenar con el sistema actual y reentrenar con datos recientes |
| Rebalanceo operativo | Cambia la ocupación sin relación con los viajes | Incluir hora y estación; medir su efecto en el diagnóstico |
| Fallas correlacionadas entre estaciones cercanas | El respaldo también está lleno | Elegir respaldo con baja dependencia con la principal |
| Efecto de la propia recomendación | Si muchos la reciben, la estación sugerida se llena | Despreciable al inicio; vigilarlo si crece el uso |
| Dependencia del feed | Cambios de formato, URL o términos de uso | Verificar licencia y términos; guardar datos crudos |
| Licencias y términos de las fuentes (feed, Open-Meteo, MaxHalford) | Restricciones de uso comercial o de atribución | Revisar términos antes del lanzamiento y mostrar la atribución |
| El histórico externo empieza después de agosto de 2022 | Menos meses de entrenamiento y menos estacionalidad | Medir la cobertura (V4) y seguir capturando |
| Clima distinto en entrenamiento y en uso | Métricas reales peores que las de validación | Comparar las fuentes (V5) o usar la misma en ambos momentos |
| Consultas con origen y destino de personas | Riesgo de reidentificación | No asociarlas a usuarios; agregarlas y limitar la retención |

**Supuestos por validar:** el costo de falla es constante al inicio; los números del ejemplo del recomendador son la probabilidad de encontrar espacio en cada estación.

## Validaciones y criterios de decisión

Antes de construir el recomendador hay que comprobar con datos que el problema existe y que las fuentes sirven. Los umbrales numéricos se fijan después de ver las primeras mediciones; hoy no hay valores de referencia.

| # | Validación | Cómo se mide | Criterio para avanzar |
| --- | --- | --- | --- |
| V1 | El problema es real: las estaciones cercanas a destinos frecuentes se llenan | Porcentaje de lecturas con 0 anclajes disponibles, por estación y franja de 15 minutos, con la captura propia | Si es poco frecuente, el producto aporta poco; umbral por definir |
| V2 | La captura es completa | Huecos, lecturas duplicadas y lecturas con `last_reported` atrasado | Cobertura continua suficiente para reconstruir la variable objetivo |
| V3 | El feed GBFS es el esperado | Abrir el JSON y confirmar versión, campos, estados de estación y licencia | Campos suficientes para definir "llena" y "fuera de servicio" |
| V4 | El histórico de MaxHalford sirve | Inicio de la serie para la Ciudad de México, frecuencia de muestreo, huecos y clima asociado | Cubre un periodo y una frecuencia útiles para predecir a 15 minutos |
| V5 | El clima de MaxHalford y el de Open-Meteo son comparables | Comparar lluvia y temperatura en los días en que ambos existen | Diferencias pequeñas; si no, usar la misma fuente en entrenamiento y en uso |
| V6 | Las estaciones vecinas fallan juntas | P(estación B llena \| estación A llena) con el histórico | Define qué tan independiente debe ser el respaldo |
| V7 | El modelo supera las líneas base | Brier score en un bloque final de días que el modelo no vio | Mejor que persistencia y que el promedio por estación y franja |
| V8 | Las probabilidades son confiables | Curva de calibración por tipo de estación | Curva cercana a la diagonal en centro y periferia |
| V9 | Las recomendaciones funcionan | Simulación sobre viajes históricos (ver abajo) | Más aciertos que "la más cercana al destino" |

**Cómo se evalúan las recomendaciones.** Para cada viaje histórico se simula la recomendación con la información que había al salir y se revisa el estado real de la estación recomendada en el momento de llegada, tomado de las capturas. Se compara contra dos alternativas: la estación más cercana al destino y la que tiene más anclajes libres al salir. El tiempo extra de búsqueda no tiene un dato observado: se estima por simulación con un costo de falla supuesto y, si se hace, se contrasta después con una prueba piloto con usuarios.

## Plan por fases y preguntas abiertas

El plan avanza en seis etapas y cada una pasa a la siguiente solo si cumple su condición.

**Validar la captura (3 días).** Condición: el flujo guarda datos crudos con marca de tiempo y permite reconstruir la variable objetivo sin huecos que lo impidan.

**Diagnosticar el histórico externo.** Medir desde cuándo cubre Ciudad de México, cada cuánto muestrea y cuántos huecos tiene, y si su clima es comparable con el de Open-Meteo. Condición: saber si sirve para entrenar a 15 minutos.

**Capturar durante 1 mes y limpiar los viajes.** Normalizar nombres de archivo y formatos de fecha, y usar solo los viajes del sistema nuevo (desde agosto de 2022).

**Línea base y primer modelo.** Condición: supera la persistencia y el promedio histórico en validación temporal.

**Recomendador.** Aplicar el puntaje de tiempo esperado y evaluar la tasa de recomendaciones exitosas.

**Fase 2 de seguridad.** Solo si la fase 1 cumple sus métricas.

**Duraciones y responsables.** La etapa 1 dura 3 días y la etapa 3 incluye 1 mes de captura; las demás duraciones se estiman al terminar la etapa 2, cuando se conozca la cobertura del histórico. Responsables: por definir. La API y la interfaz (mapa web o app) quedan para una fase posterior a la etapa 5.

**Decisiones tomadas**

Entregable final: una API que alimentará un mapa web interactivo o una app, en una fase posterior; la primera fase es datos y modelo.

Radio caminable: 500 m o menos.

Licencia del proyecto: Apache 2.0.

Clima: Open-Meteo para el clima actual y el histórico de MaxHalford para entrenar.

Entrenamiento: solo con datos del sistema nuevo, de agosto de 2022 en adelante.

**Preguntas abiertas**

¿Cuál es el costo de falla inicial, en minutos?

¿Qué términos de uso tienen el feed GBFS, Open-Meteo y MaxHalford, y son compatibles con la licencia Apache 2.0 y con un uso comercial futuro?

¿El clima de MaxHalford y el de Open-Meteo son comparables entre sí? Se averiguará en la validación V5.

En la fase de la API: ¿cuáles son la latencia objetivo, la autenticación y los límites de uso?

En la fase de la API, si se guardan las consultas, ¿cuánto tiempo se conservan?

¿Los números del ejemplo del recomendador son la probabilidad de encontrar anclaje en cada estación? Falta confirmarlo.

## Fuentes consultadas

Páginas citadas en este PRD y lo que respalda cada una. Las marcadas "sin verificar" se localizaron pero no se abrió su contenido completo.

| Fuente | Qué respalda | Estado |
| --- | --- | --- |
| [Datos abiertos de Ecobici](https://ecobici.cdmx.gob.mx/en/open-data/) | URL del feed GBFS, viajes mensuales de 2010-02 a 2026-09 y falta de histórico oficial de disponibilidad | Verificada |
| [Feed GBFS de Ecobici](https://gbfs.mex.lyftbikes.com/gbfs/gbfs.json) | Estado en vivo de las estaciones | Sin verificar el contenido |
| [Cicloestaciones (nuevo sistema)](https://datos.cdmx.gob.mx/dataset/cicloestaciones-ecobici-nuevo-sistema) | Ubicación de estaciones, corte del 17/10/2024 | Verificada |
| [MaxHalford/bike-sharing-history](https://github.com/MaxHalford/bike-sharing-history) | Histórico comunitario con clima asociado | Repositorio verificado; cobertura sin medir |
| [Open-Meteo](https://open-meteo.com/) y su [API de pronósticos históricos](https://open-meteo.com/en/docs/historical-forecast-api) | Clima por hora, licencia CC BY 4.0 y resolución de 9 a 25 km | Verificada |
| [App de Ecobici en App Store](https://apps.apple.com/us/app/ecobici/id1608397837) | La app oficial muestra disponibilidad en tiempo real | Verificada |
| [Estudio de simulación del inventario de Ecobici](https://www.sciencedirect.com/science/article/abs/pii/S2213624X21000791) | Encuesta Ecobici 2017: 68 % usa la bici para casa o trabajo | Verificada en el resumen |
| [Carpetas de investigación de la FGJ](https://datos.cdmx.gob.mx/dataset/carpetas-de-investigacion-fgj-de-la-ciudad-de-mexico) | Delitos con fecha, hora y coordenadas desde 2016 | Verificada; el portal bloquea el acceso automatizado |
| [Cymet Monroy y Larreguy (2026)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6132346) | Efecto de las estaciones sobre el delito reportado | Verificada en el resumen |
| [Postes C5 con WiFi](https://datos.cdmx.gob.mx/dataset/ubicacion-acceso-gratuito-internet-wifi-c5) | Ubicación parcial de cámaras, edición 2021 | Verificada |

Consultado el Oct 6, 2026.
