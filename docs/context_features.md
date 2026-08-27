# Context features de ReActiva

Este documento describe las variables contextuales utilizadas por ReActiva, su construcción estandarizada y la estrategia implementada en la Issue #47 para manejar segmentos con poco soporte.

## Objetivo

Incorporar contexto temporal y geográfico de forma reproducible para apoyar rankings de popularidad y mecanismos de fallback del recomendador.

Además, la implementación centraliza la construcción de features derivadas para evitar que notebooks, modelos y componentes productivos mantengan reglas duplicadas o inconsistentes.

La construcción estandarizada de features se encuentra en:

`src/reactiva/features/build_features.py`

La lógica contextual de rankings, soporte y fallback se encuentra en:

`src/reactiva/features/context.py`

---

## Feature estandarizada: season

La variable canónica de temporada se denomina:

`season`

Se deriva exclusivamente de:

`Purchase Date`

Los valores estandarizados son:

- `winter`: diciembre, enero y febrero.
- `summer`: marzo, abril y mayo.
- `monsoon`: junio, julio, agosto y septiembre.
- `post-monsoon`: octubre y noviembre.

La regla de construcción se encuentra centralizada en:

`src/reactiva/features/build_features.py`

Las funciones principales son:

- `season_from_month()`
- `season_from_date()`
- `add_season()`

Esto evita que distintos notebooks o componentes implementen manualmente su propia clasificación de temporadas.

La transformación es determinista y `add_season()` trabaja sobre una copia del DataFrame recibido.

También se normalizan entradas de temporada cuando es necesario para mantener consistencia con los valores canónicos utilizados por el proyecto.

---

## Feature estandarizada: age_group

La variable canónica de grupo etario se denomina:

`age_group`

Se deriva de:

`Age`

La clasificación estandarizada utilizada por el proyecto es:

- `Young Adult`: edad menor o igual a 25 años.
- `Adult`: edad mayor a 25 y menor a 65 años.
- `Old`: edad mayor o igual a 65 años.

La regla se encuentra centralizada en:

`src/reactiva/features/build_features.py`

Las funciones principales son:

- `age_group_from_age()`
- `add_age_group()`

La función general:

`build_features()`

permite construir de forma conjunta las features derivadas utilizadas por los componentes que necesitan tanto `season` como `age_group`.

---

## Location

`Location` se utiliza únicamente como contexto geográfico.

No debe interpretarse como:

- clima real;
- sucursal;
- tienda física;
- condición meteorológica.

Su objetivo es permitir comparar patrones de compra observados entre ubicaciones presentes en el dataset.

---

## Rankings de popularidad contextual

El módulo:

`src/reactiva/features/context.py`

permite construir rankings en cuatro niveles:

1. Popularidad global.
2. Popularidad por `season`.
3. Popularidad por `Location`.
4. Popularidad por interacción `season + Location`.

Cada ranking utiliza la cantidad histórica de compras del producto como señal de popularidad.

En caso de empate, el orden se resuelve de forma determinista por nombre de producto para mantener reproducibilidad.

La construcción de `season` no se redefine dentro de este módulo.

`context.py` consume la feature estandarizada desde:

`src/reactiva/features/build_features.py`

---

## Soporte mínimo

Los segmentos contextuales pueden contener pocas observaciones.

Para evitar depender de rankings construidos con grupos demasiado pequeños se define:

`DEFAULT_MIN_SUPPORT = 20`

Este valor es configurable.

Si un segmento no alcanza el soporte mínimo, ese nivel contextual no se utiliza y se continúa con el siguiente nivel del fallback.

El soporte corresponde actualmente a la cantidad de transacciones disponibles dentro del segmento evaluado.

---

## Estrategia de fallback

La estrategia implementada sigue este orden:

`season + Location`

↓

`Location`

↓

`season`

↓

`Global`

El ranking global funciona como respaldo final y no está sujeto al mínimo de soporte contextual.

El objetivo es evitar recomendaciones vacías cuando una combinación específica de contexto contiene pocas observaciones.

---

## Construcción progresiva del Top K

El fallback puede completar el ranking utilizando más de un nivel.

Por ejemplo:

- un segmento `season + Location` puede aportar algunos productos;
- `Location` puede completar los candidatos restantes;
- si todavía faltan productos, se continúa con `season`;
- finalmente se utiliza el ranking global.

Un producto nunca se agrega más de una vez.

---

## Trazabilidad

La función:

`recommend_contextual_popularity()`

devuelve además una traza que permite conocer:

- el nivel contextual evaluado;
- el soporte disponible;
- si el nivel fue utilizado;
- el motivo por el cual fue utilizado o descartado;
- los productos agregados desde ese nivel.

Esto permite auditar posteriormente por qué una recomendación utilizó contexto específico o recurrió a un nivel de fallback menos específico.

---

## Integración con el código existente

Como parte de la estandarización se revisaron los componentes que construían o consumían estas features.

Actualmente:

- `src/reactiva/features/build_features.py` es la fuente única para construir `season` y `age_group`;
- `src/reactiva/features/context.py` reutiliza `add_season()` para rankings y fallback contextual;
- `src/reactiva/recommender/recommender.py` reutiliza la construcción estandarizada de `season`;
- `src/reactiva/modeling/model_comparasion_270day_metrics_updated_threshold_070.ipynb` reutiliza `build_features()` para obtener `season` y `age_group`;
- `notebooks/02_recommender_feasibility.ipynb` reutiliza `add_season()` para el análisis de soporte del fallback.

La estandarización no modifica la lógica matemática de los modelos ni los criterios existentes de recomendación.

El objetivo del cambio es eliminar definiciones duplicadas y garantizar que todos los consumidores utilicen los mismos nombres y reglas para las features derivadas.

---

## Validación del notebook de comparación de modelos

Después de reemplazar la creación manual de `season` y `age_group` por `build_features()`, el notebook de comparación de modelos fue ejecutado nuevamente desde un kernel limpio.

La partición temporal se mantuvo sin cambios:

- fecha máxima: `2024-12-30`;
- fecha de corte: `2024-04-04`;
- filas de entrenamiento: `6281`;
- filas de holdout: `3719`;
- clientes evaluados: `1877`;
- temporadas disponibles: `monsoon`, `post-monsoon`, `summer` y `winter`.

Las métricas finales de los modelos también se mantuvieron sin cambios.

Esto confirma que la centralización de features no alteró el comportamiento de la evaluación existente.

---

## Validación del notebook de factibilidad

El notebook:

`notebooks/02_recommender_feasibility.ipynb`

fue actualizado para utilizar `add_season()` en lugar de volver a implementar manualmente la clasificación por temporada.

Luego se ejecutó completamente desde un kernel limpio.

El análisis de `Location + season` mantuvo los mismos resultados principales:

- 80 segmentos;
- promedio de 125 transacciones por segmento;
- mediana de 124.5;
- mínimo de 67 transacciones;
- máximo de 208 transacciones;
- promedio de 23.02 productos distintos por segmento;
- 40 segmentos con los 24 productos;
- 23 segmentos con menos de 100 transacciones;
- ningún segmento con menos de 50 transacciones.

Esto confirma que la estandarización no modificó los resultados del análisis de factibilidad.

---

## Pruebas automáticas

Las pruebas específicas de contexto se encuentran en:

`tests/test_context.py`

Actualmente verifican, entre otros puntos:

- asignación correcta de temporadas;
- rechazo de meses inválidos;
- normalización de nombres de temporada;
- no modificación del DataFrame original;
- construcción estandarizada de `age_group`;
- construcción conjunta de features;
- construcción de rankings globales y contextuales;
- aplicación del soporte mínimo;
- fallback hacia niveles menos específicos;
- existencia de fallback global;
- ausencia de productos repetidos.

La suite completa del proyecto fue ejecutada después de los cambios:

`19 passed`

Además, ambos notebooks modificados fueron ejecutados completamente desde un kernel limpio sin errores.

Esto confirma que la centralización de features y la integración de la Issue #47 no introdujeron regresiones detectadas por las pruebas existentes.