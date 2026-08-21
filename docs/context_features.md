# Context features de ReActiva

Este documento describe las variables contextuales implementadas para la Issue #47 y la estrategia utilizada para manejar grupos con poco soporte.

## Objetivo

Incorporar contexto temporal y geográfico de forma reproducible para apoyar rankings de popularidad y futuros fallbacks del recomendador.

La lógica se encuentra implementada en:

`src/reactiva/features/context.py`

## Season_India

La variable `Season_India` se deriva exclusivamente de `Purchase Date`.

Se utiliza la siguiente clasificación:

- `Winter`: diciembre, enero y febrero.
- `Summer`: marzo, abril y mayo.
- `Monsoon`: junio, julio, agosto y septiembre.
- `Post-Monsoon`: octubre y noviembre.

La transformación es determinista y no modifica el DataFrame original recibido por la función.

También se normalizan nombres de temporada utilizados previamente en el proyecto, por ejemplo:

- `winter` → `Winter`
- `summer` → `Summer`
- `post-monsoon` → `Post-Monsoon`

Esto permite mantener compatibilidad con código previo sin modificarlo.

## Location

`Location` se utiliza únicamente como contexto geográfico.

No debe interpretarse como:

- clima real;
- sucursal;
- tienda física;
- condición meteorológica.

Su objetivo es permitir comparar patrones de compra observados entre ubicaciones del dataset.

## Rankings de popularidad

El módulo permite construir rankings en cuatro niveles:

1. Popularidad global.
2. Popularidad por `Season_India`.
3. Popularidad por `Location`.
4. Popularidad por interacción `Season_India + Location`.

Cada ranking utiliza la cantidad histórica de compras del producto como señal de popularidad.

En caso de empate, el orden se resuelve de forma determinista por nombre de producto para mantener reproducibilidad.

## Soporte mínimo

Los segmentos contextuales pueden contener pocas observaciones.

Para evitar depender de rankings construidos con grupos demasiado pequeños se define:

`DEFAULT_MIN_SUPPORT = 20`

Este valor es configurable.

Si un segmento no alcanza el soporte mínimo, ese nivel contextual no se utiliza y se continúa con el siguiente nivel del fallback.

El soporte corresponde actualmente a la cantidad de transacciones disponibles dentro del segmento evaluado.

## Estrategia de fallback

La estrategia implementada sigue este orden:

`Season_India + Location`

↓

`Location`

↓

`Season_India`

↓

`Global`

El ranking global funciona como respaldo final y no está sujeto al mínimo de soporte contextual.

El objetivo es evitar recomendaciones vacías cuando una combinación específica de contexto tiene pocos datos.

## Construcción progresiva del Top K

El fallback puede completar el ranking utilizando más de un nivel.

Ejemplo:

- un segmento `Season_India + Location` puede aportar algunos productos;
- `Location` puede completar los candidatos restantes;
- si todavía faltan productos, se continúa con `Season_India`;
- finalmente se utiliza el ranking global.

Un producto nunca se agrega más de una vez.

## Trazabilidad

La función `recommend_contextual_popularity()` devuelve además una traza con:

- nivel evaluado;
- soporte disponible;
- si el nivel fue utilizado;
- motivo por el cual fue utilizado o descartado;
- productos agregados desde ese nivel.

Esto permite posteriormente auditar por qué una recomendación utilizó contexto específico o recurrió a un fallback.

## Integración con código existente

La implementación de esta Issue se agregó como un módulo nuevo.

No se modificó la lógica existente del recomendador ni los modelos desarrollados previamente.

El objetivo es que esta lógica pueda ser reutilizada posteriormente por otros componentes sin duplicar reglas de temporada, soporte o fallback.

## Pruebas automáticas

Se agregó:

`tests/test_context.py`

Las pruebas verifican:

- asignación correcta de temporadas;
- rechazo de meses inválidos;
- normalización de nombres de temporada;
- no modificación del DataFrame original;
- construcción de rankings globales y contextuales;
- aplicación del soporte mínimo;
- fallback hacia niveles menos específicos;
- existencia de fallback global;
- ausencia de productos repetidos.

Al finalizar la implementación se ejecutó la suite completa del proyecto:

`17 passed`

Esto confirma que los nuevos componentes funcionan y que no se introdujeron regresiones en las pruebas existentes.