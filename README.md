# ReActiva Recommender

Proyecto Final de Data Science desarrollado por **GMJ Analytics**.

## Objetivo

Desarrollar un sistema de recomendación orientado a la reactivación comercial que permita:

- Identificar clientes inactivos mediante la regla de negocio vigente de **270 días o más sin compras**.
- Generar recomendaciones personalizadas de productos para incentivar una nueva compra.
- Incorporar contexto estacional y geográfico como soporte del sistema de recomendación.
- Aplicar mecanismos de fallback cuando no exista historial suficiente para una recomendación personalizada.
- Convertir los resultados en acciones comerciales concretas y trazables.

ReActiva **no estima una probabilidad binaria de recompra**.

La condición de inactividad se determina mediante una regla observable basada en la fecha de última compra, mientras que los modelos del proyecto se utilizan para decidir **qué productos tiene sentido ofrecer a cada cliente** con el objetivo de incentivar su reactivación.

## Equipo

- Jesús Elías
- Martín Darío Fernández
- Gabriel Gómez

## Flujo de trabajo y protección de main

La rama `main` se encuentra protegida y no se permiten modificaciones directas sobre ella.

El desarrollo del proyecto se realiza mediante un flujo de trabajo basado en Issues, ramas y Pull Requests:

1. Las tareas se seleccionan desde las Issues habilitadas en GitHub Project.
2. Cada integrante se asigna la Issue que va a desarrollar.
3. Antes de comenzar una nueva tarea se actualiza la rama `main` local.
4. Cada Issue se desarrolla en una rama independiente creada a partir de `main`.
5. Los cambios se registran mediante commits y se publican en la rama correspondiente.
6. La integración a `main` se realiza exclusivamente mediante Pull Request.
7. La rama `main` se encuentra configurada para impedir el merge de un Pull Request hasta contar con al menos una aprobación de revisión por parte de otro integrante del equipo. Esta regla aplica también cuando el autor del PR es quien posee permisos para realizar el merge.
8. Una vez aprobado y mergeado el PR, la Issue asociada se considera finalizada.

Este flujo permite mantener la trazabilidad de las tareas, los aportes individuales y las revisiones realizadas por el equipo durante el desarrollo del proyecto.

## Estado

ReActiva se encuentra actualmente en una etapa avanzada de integración y cierre del MVP.

El proyecto cuenta con componentes funcionales de:

- carga y almacenamiento de datos;
- auditoría y validación;
- análisis exploratorio;
- preparación de datos;
- ingeniería de features;
- comparación y evaluación de modelos de recomendación;
- recomendación para clientes inactivos;
- contexto y mecanismos de fallback;
- aplicación interactiva mediante Streamlit;
- almacenamiento y persistencia en AWS S3;
- logging estructurado;
- pruebas automáticas;
- ejecución mediante Docker;
- generación reproducible de tablas para Power BI;
- dashboard inicial de Power BI.

Las principales tareas restantes se concentran en la consolidación del ranking comercial final, automatización del flujo de reactivación, monitoreo, pipeline end-to-end, ampliación de Power BI y preparación de la entrega final.

### Instalación del paquete local

El archivo `pyproject.toml` define el paquete `reactiva` bajo la estructura `src/`.

La instalación editable puede realizarse desde la raíz del repositorio mediante:

```bash
python -m pip install -e .
```

Esto permite importar los módulos del paquete `reactiva` desde distintos componentes del proyecto sin depender de modificaciones manuales de rutas.

Por ejemplo:

```python
from reactiva.data.load_data import load_data
```

La lógica reutilizable del proyecto se centraliza principalmente en:

```text
src/reactiva/
```

evitando, cuando es posible, mantener implementaciones duplicadas entre notebooks, Streamlit y los módulos productivos.

## Arquitectura actual del repositorio

La estructura principal del proyecto es actualmente:

```text
ReActiva-recommender/
│
├── .github/
│
├── api/                  # placeholder legado pendiente de eliminación
│
├── app/
│   ├── app.py
│   └── Dockerfile
│
├── artifacts/
│
├── dashboard/
│   ├── ReActiva_EDA_Quality.pbip
│   └── data/
│
├── data/
│
├── docs/
│   ├── context_features.md
│   ├── data_dictionary.csv
│   └── troubleshooting/
│       └── README.md
│
├── notebooks/
│   ├── 01_eda_reactiva.ipynb
│   └── 02_recommender_feasibility.ipynb
│
├── reports/
│
├── src/
│   └── reactiva/
│       ├── config.py
│       │
│       ├── data/
│       │   ├── audit_data.py
│       │   ├── build_bi_eda_tables.py
│       │   ├── load_data.py
│       │   ├── save_results.py
│       │   └── validate_data.py
│       │
│       ├── features/
│       │   ├── build_features.py
│       │   └── context.py
│       │
│       ├── modeling/
│       │   ├── backtest.py
│       │   ├── evaluate.py
│       │   ├── model_comparasion_270day_metrics_updated_threshold_070.ipynb
│       │   ├── optuna_gb_classification.ipynb
│       │   ├── predict_matriz.py
│       │   └── train.py
│       │
│       ├── monitoring/
│       │   ├── data_quality.py
│       │   └── drift.py
│       │
│       ├── pipeline/
│       │   └── run_pipeline.py
│       │
│       ├── recommender/
│       │   └── recommender.py
│       │
│       └── utils/
│
├── tests/
│
├── .dockerignore
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

Algunas carpetas y archivos forman parte de responsabilidades todavía pendientes del MVP y no contienen aún su implementación definitiva.

La carpeta `api/` permanece temporalmente en el repositorio únicamente como placeholder legado de la planificación inicial.

La decisión arquitectónica vigente es **no desarrollar una API independiente dentro del MVP y utilizar Streamlit como aplicación/demo funcional**.

La eliminación física del placeholder `api/` se realizará mediante el flujo normal de rama, commit, Pull Request y revisión.

## Decisión de arquitectura: Streamlit como aplicación funcional del MVP

Durante la planificación inicial de ReActiva se contempló implementar una API independiente además de Streamlit.

Luego de revisar el alcance funcional vigente, el estado real del producto y los criterios de evaluación del Proyecto Final, el equipo decidió **no incorporar una API REST independiente dentro del MVP**.

Streamlit será la aplicación/demo funcional utilizada para exponer las capacidades de ReActiva.

La lógica de negocio, preparación de datos, features y recomendación permanece centralizada en módulos reutilizables dentro de:

```text
src/reactiva/
```

De esta manera, Streamlit funciona como capa de interacción sin convertirse en la ubicación exclusiva de la lógica del sistema.

Esta decisión permite:

- evitar una capa adicional de infraestructura sin una necesidad funcional concreta;
- reducir duplicación de lógica;
- reducir puntos de fallo y complejidad de despliegue;
- simplificar pruebas y mantenimiento del MVP;
- concentrar el desarrollo restante en funcionalidades directamente relacionadas con el objetivo de negocio;
- mantener la arquitectura preparada para incorporar una API posteriormente si aparece una necesidad real de integración externa.

Como consecuencia de esta decisión:

- Streamlit se adopta como aplicación/demo funcional del MVP;
- no se desarrollarán endpoints REST dentro del alcance actual;
- la lógica reutilizable debe permanecer desacoplada de Streamlit dentro de `src/reactiva`;
- el placeholder `api/` será retirado del repositorio;
- las Issues exclusivamente asociadas a la API serán cerradas como `Not planned`;
- las Issues mixtas que continúen aportando valor serán reformuladas para referirse a Streamlit, al pipeline o a la activación comercial según corresponda;
- una futura API podrá incorporarse como evolución del producto si surge una necesidad concreta de integración con sistemas externos.

Esta decisión representa una **reducción deliberada de complejidad arquitectónica**, no una limitación accidental del desarrollo.

## Flujo técnico actual

El flujo funcional vigente puede representarse de la siguiente manera:

```text
Dataset histórico
        │
        ▼
Amazon S3
        │
        ▼
Carga de datos
        │
        ▼
Auditoría
        │
        ▼
Validación y preparación
        │
        ▼
Ingeniería de features
        │
        ├──────────────► EDA
        │
        ├──────────────► Análisis de factibilidad
        │
        ▼
Identificación de clientes inactivos
        │
        │  regla: >= 270 días sin compras
        │
        ▼
Sistema de recomendación
        │
        ├── User-Based Collaborative Filtering
        │      modelo principal seleccionado
        │
        └── Fallback contextual
               │
               ├── season + Location
               ├── Location
               ├── season
               └── Global
        │
        ▼
Recomendaciones de productos
        │
        ▼
Streamlit / activación comercial
        │
        ▼
Resultados, S3 y logging
        │
        ▼
Power BI / seguimiento
```

La lógica central del producto es:

```text
Historial de compras
        ↓
¿Cliente inactivo >= 270 días?
        ↓
Sí
        ↓
¿Qué productos tiene sentido ofrecerle?
        ↓
Recomendaciones
        ↓
Acción de reactivación
```

El proyecto no intenta determinar mediante un clasificador binario si el cliente volverá o no a comprar.

## Fuente de datos

La fuente principal de información del proyecto se encuentra almacenada en Amazon S3.

La ruta del dataset se obtiene mediante configuración externa a través de:

```text
DATASET_URI
```

y no se encuentra hardcodeada directamente dentro del código.

La configuración general se centraliza en:

```text
src/reactiva/config.py
```

Entre las variables de entorno actualmente contempladas se encuentran:

```text
DATASET_URI
S3_BUCKET
MATRIX_URI
AWS_REGION
API_KEY
USUARIO_ADMIN
PASSWORD_ADMIN
```

Algunas configuraciones podrán ser revisadas o retiradas durante la limpieza final si dejan de ser necesarias para la arquitectura definitiva.

Las credenciales, contraseñas, API keys, tokens y secretos no deben almacenarse directamente en el código ni versionarse en GitHub.

El archivo privado:

```text
.env
```

debe mantenerse fuera del repositorio.

## Auditoría del dataset

El proyecto cuenta con una auditoría automatizada implementada en:

```text
src/reactiva/data/audit_data.py
```

Esta auditoría permite analizar, entre otros aspectos:

- dimensiones del dataset;
- nombres de columnas;
- tipos de datos;
- valores nulos;
- duplicados;
- cardinalidad;
- rangos numéricos;
- fechas;
- valores extremos;
- concentración de categorías;
- concentración de productos;
- consistencia entre registros online y offline;
- estructura de compras por cliente.

El objetivo de esta etapa es cuantificar la calidad de los datos antes de aplicar transformaciones o utilizarlos en componentes posteriores del proyecto.

Los valores extremos detectados no se eliminan automáticamente únicamente por tratarse de outliers estadísticos, ya que un valor extremo no necesariamente representa un dato incorrecto.

## Validación y preparación reproducible

La lógica de validación y preparación se encuentra principalmente en:

```text
src/reactiva/data/validate_data.py
```

Actualmente se contemplan controles relacionados con:

- esquema esperado;
- presencia de columnas;
- tipos de datos;
- normalización de valores;
- fechas;
- rangos numéricos;
- valores faltantes;
- categorías;
- consistencia entre variables;
- reglas particulares para compras online y offline;
- detección y tratamiento de duplicados.

La estrategia de deduplicación incorpora:

```text
Transaction ID
```

como parte de la identificación de una operación.

Esto evita considerar erróneamente como duplicadas compras legítimas realizadas por un mismo cliente sobre un mismo producto y fecha.

La preparación actual conserva las 10.000 transacciones válidas del dataset.

## Actualización del dataset

El dataset actual incorpora los campos:

```text
Customer Full Name
Customer Email
```

para que el flujo de reactivación pueda identificar al cliente de forma legible y disponer de un medio de contacto.

Estos campos fueron incorporados de forma sintética con fines operativos del proyecto:

- `Customer Full Name`: permite identificar al cliente más allá de su `Customer ID`.
- `Customer Email`: permite representar el canal de contacto necesario para una acción de reactivación.

El dataset vigente contiene:

- **10.000 filas**;
- **27 columnas**;
- **3.291 clientes únicos**.

El esquema actual ya no incluye:

```text
Frequency of Purchases
```

Esta modificación fue incorporada a los procesos de auditoría, validación, preparación, documentación y análisis que consumen el dataset.

El diccionario de datos actualizado se encuentra disponible en:

[`docs/data_dictionary.csv`](docs/data_dictionary.csv)

Los campos `Customer Full Name` y `Customer Email` deben considerarse variables operativas incorporadas para representar el flujo de contacto y no variables originales obtenidas del dataset fuente.

## Criterio actual de inactividad

El criterio vigente del proyecto para considerar a un cliente inactivo es:

```text
days_since_last_purchase >= 270
```

Es decir, **270 días o más desde su última compra**.

Este criterio reemplaza el horizonte de 180 días contemplado durante etapas iniciales del proyecto.

Las referencias históricas a 180 días corresponden a una versión anterior del alcance y no representan la lógica funcional vigente.

El criterio de 270 días constituye una **regla operativa observable** y no la salida de un modelo predictivo.

Un cliente que cumple esta condición puede ser considerado candidato para una acción de reactivación.

Esto no implica afirmar que el cliente haya abandonado definitivamente la empresa ni garantiza que vaya a volver a comprar.

## Análisis exploratorio de datos

El EDA reproducible se encuentra en:

```text
notebooks/01_eda_reactiva.ipynb
```

El notebook analiza distintas dimensiones del comportamiento de compra, incluyendo:

- clientes;
- transacciones;
- fechas;
- evolución temporal;
- canal online/offline;
- ubicación;
- categorías;
- productos;
- marcas;
- talles;
- edad;
- género;
- importes de compra;
- cantidades;
- descuentos;
- devoluciones;
- suscripciones;
- métodos de pago;
- cargos de envío;
- tiempos de entrega.

También incluye análisis de relaciones entre variables.

Para variables numéricas se utiliza, cuando corresponde:

```text
Correlación de Spearman
```

y para relaciones entre variables categóricas:

```text
Cramér's V
```

Las variables relacionadas exclusivamente con operaciones online son analizadas teniendo en cuenta que determinados valores presentes en compras offline representan condiciones estructurales y no necesariamente valores faltantes.

Entre los resultados observados existe concentración a nivel de categoría, aunque no se observa un único producto que domine ampliamente el dataset.

El producto individual más frecuente representa aproximadamente el 8,7 % de las compras y los cinco productos más frecuentes concentran aproximadamente el 40,7 %.

Los resultados del EDA se mantienen como evidencia descriptiva y no se interpretan automáticamente como relaciones causales.

## Análisis de factibilidad del recomendador

El análisis de factibilidad se encuentra documentado en:

```text
notebooks/02_recommender_feasibility.ipynb
```

Este notebook estudia las características del dataset que afectan directamente la posibilidad de construir un sistema de recomendación.

Entre los análisis realizados se encuentran:

- matriz cliente-producto;
- sparsity;
- profundidad del historial por cliente;
- cold start;
- clientes inactivos;
- popularidad;
- cobertura de catálogo;
- long tail;
- coocurrencia;
- soporte entre productos;
- afinidades item-item;
- estabilidad temporal;
- crecimiento de información al incorporar nuevas transacciones;
- soporte disponible por ubicación y temporada.

La matriz cliente-producto presenta actualmente una sparsity aproximada de:

```text
88,26 %
```

Esto indica que existe información suficiente para construir mecanismos de personalización, aunque una parte de los clientes posee historiales relativamente cortos.

Por esta razón el sistema contempla mecanismos de fallback para escenarios donde la información individual disponible no sea suficiente.

El catálogo utilizado en estos análisis contiene 24 productos.

## Construcción centralizada de features

Las features derivadas utilizadas por diferentes componentes del proyecto se centralizan en:

```text
src/reactiva/features/build_features.py
```

Esto permite evitar que notebooks, modelos, Streamlit y recomendadores mantengan distintas implementaciones de una misma regla.

Entre las features actualmente centralizadas se encuentran:

```text
season
age_group
```

### season

La variable:

```text
season
```

se deriva de:

```text
Purchase Date
```

Los valores estandarizados son:

- `winter`;
- `summer`;
- `monsoon`;
- `post-monsoon`.

### age_group

La variable:

```text
age_group
```

se deriva de `Age`.

Las reglas vigentes son:

- `Young Adult`: edad menor o igual a 25 años;
- `Adult`: edad mayor a 25 y menor a 65 años;
- `Old`: edad mayor o igual a 65 años.

La documentación técnica detallada se encuentra en:

[`docs/context_features.md`](docs/context_features.md)

## Uso de Location

La variable:

```text
Location
```

se utiliza exclusivamente como contexto geográfico.

No debe interpretarse como:

- sucursal;
- tienda física;
- clima real;
- condición meteorológica.

Su utilización permite estudiar y aprovechar diferencias observadas entre las ubicaciones existentes dentro del dataset.

## Modelado y comparación de recomendadores

La comparación principal de modelos se encuentra en:

```text
src/reactiva/modeling/model_comparasion_270day_metrics_updated_threshold_070.ipynb
```

El notebook evalúa distintos enfoques utilizando una misma separación temporal para asegurar una comparación consistente.

La evaluación actual utiliza:

```text
Fecha máxima: 2024-12-30
Fecha de corte: 2024-04-04
```

La partición resultante contiene:

- 6.281 filas de entrenamiento;
- 3.719 filas de holdout;
- 1.877 clientes presentes tanto en entrenamiento como en holdout y disponibles para evaluación.

El período final de 270 días se reserva como holdout.

La información posterior al corte no es utilizada para construir las recomendaciones evaluadas.

Actualmente se comparan los siguientes enfoques:

1. User-Based Collaborative Filtering.
2. Frequency-weighted User-Based.
3. Content-Based.
4. Popularity.
5. Item-Based Collaborative Filtering.
6. Classification.
7. Hybrid User-Based CF + Popularity Fallback.

Los enfoques anteriores forman parte de la comparación experimental y no representan necesariamente componentes simultáneos del sistema productivo.

Los resultados principales registrados para Top 5 son:

| Modelo | Precision@5 | Recall@5 | Hit Rate@5 |
|---|---:|---:|---:|
| User-Based | 0.0938 | 0.2725 | 0.3841 |
| Frequency-weighted User-Based | 0.0893 | 0.2230 | 0.3239 |
| Content-Based | 0.0884 | 0.2254 | 0.3277 |
| Popularity | 0.1290 | 0.4079 | 0.5440 |
| Item-Based CF | 0.1139 | 0.3565 | 0.4928 |
| Classification | 0.1078 | 0.3418 | 0.4681 |
| Hybrid | 0.0952 | 0.2896 | 0.4033 |

La evaluación no se limita únicamente a Precision, Recall y Hit Rate.

También se incorporan métricas como:

- NDCG;
- MAP;
- Long-tail Precision;
- Long-tail Recall;
- Long-tail Hit Rate;
- Long-tail Share;
- Long-tail Catalog Coverage;
- Average Score;
- Sparsity.

Esto permite evaluar los modelos desde diferentes perspectivas y no únicamente por la cantidad de coincidencias entre productos recomendados y compras futuras.

### Modelo seleccionado

Aunque el modelo de popularidad obtuvo mejores métricas globales en algunas dimensiones, concentra sus recomendaciones en los productos más populares y presenta un desempeño limitado respecto de diversidad y long tail.

Por este motivo se seleccionó:

```text
User-Based Collaborative Filtering
```

como recomendador principal.

La decisión busca equilibrar:

- capacidad predictiva;
- personalización;
- diversidad;
- exposición a productos menos populares;
- utilidad comercial del ranking.

## Enfoque de clasificación

Dentro de la comparación existe también un enfoque denominado:

```text
Classification
```

Este componente **no predice si un cliente recomprará o no**.

Su objetivo experimental es estimar una categoría futura relevante para el cliente y utilizar esa información como señal de recomendación.

Por lo tanto, su presencia en los notebooks de modelado no contradice la decisión de no utilizar un modelo binario de propensión de recompra.

## Optimización mediante Optuna

El proyecto incorpora optimización de hiperparámetros mediante:

```text
Optuna
```

en el notebook:

```text
src/reactiva/modeling/optuna_gb_classification.ipynb
```

Actualmente se optimiza el:

```text
GradientBoostingClassifier
```

utilizado dentro del enfoque experimental de clasificación para recomendación.

La optimización mantiene:

- la misma ventana temporal;
- los mismos clientes evaluables;
- las mismas métricas principales utilizadas en la comparación de modelos.

La ejecución registrada utiliza 100 trials.

El mejor trial registrado obtuvo aproximadamente:

```text
Precision@5: 0.1135
Recall@5:    0.3512
HitRate@5:   0.4823
```

## Recomendador canónico

La implementación reutilizable del recomendador se encuentra centralizada en:

```text
src/reactiva/recommender/recommender.py
```

Esta implementación funciona como fuente canónica para evitar mantener diferentes copias de la lógica de recomendación.

Actualmente se conserva la lógica de:

```text
User-Based Collaborative Filtering
```

basada en similitud entre clientes.

El flujo identifica clientes inactivos según el criterio vigente y genera recomendaciones utilizando información histórica disponible.

También se dispone de recomendación mediante similitud de productos a través de:

```python
get_recommendations_items()
```

utilizada por componentes interactivos del proyecto.

La matriz de similitud se carga cuando es requerida y puede mantenerse en memoria durante la ejecución.

### Evolución pendiente del ranking comercial

La salida final del recomendador debe evolucionar hacia una separación explícita entre:

```text
Top 3 de alta afinidad
+
hasta Top 3 de oportunidad
```

Las recomendaciones de oportunidad estarán orientadas a productos de menor rotación únicamente cuando exista una señal real de afinidad con el cliente.

Un producto no deberá ser recomendado únicamente por pertenecer al long tail.

Esta evolución forma parte del trabajo pendiente del ranking comercial final.

## Contexto y fallback

La lógica contextual se encuentra en:

```text
src/reactiva/features/context.py
```

Actualmente pueden generarse rankings en cuatro niveles:

1. popularidad global;
2. popularidad por `season`;
3. popularidad por `Location`;
4. popularidad por interacción `season + Location`.

Para evitar utilizar segmentos contextuales construidos con muy pocas observaciones se define un soporte mínimo configurable.

El valor por defecto actual es:

```text
DEFAULT_MIN_SUPPORT = 20
```

Cuando un segmento no alcanza ese soporte, el sistema continúa hacia un nivel menos específico.

La secuencia implementada es:

```text
season + Location
        ↓
Location
        ↓
season
        ↓
Global
```

El fallback funciona como mecanismo de cobertura cuando el recomendador principal no dispone de candidatos utilizables.

La función contextual devuelve además información de trazabilidad que permite identificar:

- nivel evaluado;
- soporte disponible;
- si el nivel fue utilizado;
- motivo por el cual se utilizó o descartó;
- productos incorporados desde ese nivel.

## Cobertura funcional del recomendador

Durante las validaciones realizadas sobre el criterio vigente de 270 días se identificaron:

```text
1.028 clientes inactivos
```

y el flujo de recomendación consiguió obtener recomendaciones para todos ellos:

```text
0 clientes sin recomendación
```

Este resultado representa una validación de **cobertura funcional**.

No debe interpretarse como efectividad comercial real ni como garantía de que cada recomendación vaya a producir una compra.

## Streamlit

La aplicación interactiva del proyecto se encuentra en:

```text
app/app.py
```

y está desarrollada utilizando:

```text
Streamlit
```

Streamlit constituye la **aplicación/demo funcional del MVP**.

La aplicación permite interactuar con diferentes componentes de ReActiva sin trasladar la lógica de negocio principal fuera de los módulos reutilizables de `src/reactiva`.

Actualmente contiene áreas para:

1. interacción individual;
2. carga masiva;
3. explorador 360 y CRM;
4. auditoría y logs para usuarios con acceso administrativo.

### Interacción individual

La aplicación permite trabajar tanto con:

- clientes existentes;
- perfiles nuevos sin historial.

Se utilizan datos relacionados con:

- perfil;
- edad;
- género;
- ubicación;
- compra;
- categoría;
- marca;
- producto;
- canal de venta;
- variables operativas.

Para perfiles sin historial suficiente, donde un recomendador colaborativo no dispone de información individual, se utilizan mecanismos de fallback basados en la información disponible.

### Carga masiva

Streamlit permite trabajar con conjuntos de transacciones y aplicar controles de validación antes de continuar con el flujo.

Los datos pueden almacenarse en S3 cuando la configuración y los permisos disponibles lo permiten.

### Explorador 360 y CRM

La aplicación dispone de una vista orientada al análisis individual de clientes.

Entre las métricas calculadas se encuentran:

- cantidad de compras;
- gasto total;
- ticket promedio;
- categoría más frecuente;
- marca más frecuente;
- ubicación;
- última compra;
- días de inactividad;
- historial de compras;
- estado asociado al criterio de inactividad.

## Logging estructurado

El sistema de logging se encuentra implementado en:

```text
src/reactiva/utils/logger.py
```

Los registros se generan en formato JSON.

Pueden escribirse:

- en consola;
- en archivos persistentes dentro de `artifacts/logs`.

El logger permite registrar:

- eventos;
- errores;
- excepciones;
- información estructurada adicional.

También incorpora sanitización automática de variables cuyos nombres puedan indicar contenido sensible.

Entre las palabras detectadas se encuentran:

```text
password
secret
token
api_key
access_key
credential
```

Cuando se detectan estos campos, su valor se reemplaza por:

```text
[REDACTED]
```

Esto reduce el riesgo de que credenciales o secretos aparezcan accidentalmente en registros del sistema.

## AWS S3

Amazon S3 forma parte de la arquitectura actual de ReActiva.

Se utiliza como fuente o destino para distintos elementos del proyecto, entre ellos:

- dataset histórico;
- resultados procesados;
- archivos generados;
- artefactos utilizados por componentes del recomendador.

La comunicación con AWS se realiza utilizando configuración y credenciales externas al código.

Las credenciales nunca deben incorporarse dentro de archivos versionados en GitHub.

## Power BI

El proyecto incluye un dashboard interactivo de EDA y calidad desarrollado en Power BI y versionado mediante Power BI Project (PBIP).

El proyecto se encuentra en:

```text
dashboard/ReActiva_EDA_Quality.pbip
```

Actualmente contiene dos páginas principales:

- `Resumen Ejecutivo`: KPIs generales, evolución temporal, distribución por categoría y canal, y métricas de calidad del dataset.
- `Análisis Comercial`: rankings de productos, marcas y ubicaciones, estado y rango etario de clientes, y comportamiento por método de pago.

El dashboard continuará evolucionando para incorporar información relacionada con:

- clientes candidatos a reactivación;
- recomendaciones;
- productos;
- oportunidades comerciales;
- métricas del sistema;
- seguimiento del flujo de reactivación.

### Generación de tablas para Power BI

Las tablas utilizadas por el dashboard se generan de forma reproducible mediante:

```bash
python -m reactiva.data.build_bi_eda_tables
```

El proceso crea o reemplaza archivos dentro de:

```text
dashboard/data/
```

Entre ellos:

- `bi_transactions.csv`;
- `bi_customers.csv`;
- `bi_products.csv`;
- `bi_calendar.csv`;
- `bi_quality_summary.csv`;
- `bi_quality_columns.csv`.

La generación reutiliza componentes canónicos del proyecto para validación y construcción de features, evitando duplicar lógica de negocio.

### Configuración local de la fuente

Las consultas de Power BI utilizan el parámetro:

```text
RutaDatosBI
```

como ubicación base para los archivos CSV.

Al trabajar desde una nueva máquina o ubicación del repositorio debe modificarse este parámetro para que apunte a:

```text
dashboard/data
```

Los archivos locales de caché y configuración de Power BI no se versionan.

La estrategia definitiva de publicación y distribución del dashboard se definirá de acuerdo con el alcance final de la entrega.

## Dependencias

El archivo canónico de dependencias del proyecto es:

```text
requirements.txt
```

ubicado en la raíz del repositorio.

Se eliminaron listas de dependencias duplicadas para evitar diferencias entre componentes del proyecto.

Entre las principales tecnologías presentes se encuentran:

- Python;
- pandas;
- NumPy;
- scikit-learn;
- SciPy;
- Streamlit;
- boto3;
- botocore;
- s3fs;
- matplotlib;
- seaborn;
- Optuna;
- pytest;
- python-dotenv.

`Uvicorn` continúa actualmente presente entre las dependencias históricas del entorno, aunque **no forma parte de la arquitectura funcional del MVP ni es necesario para ejecutar Streamlit**.

Su permanencia será revisada durante la limpieza final de dependencias junto con cualquier otra librería que haya dejado de ser utilizada.

## Instalación del entorno

Se recomienda trabajar dentro de un entorno virtual.

Desde la raíz del repositorio:

```bash
python -m venv .venv
```

En Windows:

```bash
.venv\Scripts\activate
```

Luego se instalan las dependencias mediante:

```bash
python -m pip install -r requirements.txt
```

y el paquete local:

```bash
python -m pip install -e .
```

## Ejecución de Streamlit

Con el entorno configurado y las variables necesarias disponibles:

```bash
streamlit run app/app.py
```

## Docker

El proyecto cuenta con una configuración funcional de Docker para la aplicación Streamlit.

El archivo correspondiente se encuentra en:

```text
app/Dockerfile
```

La imagen utiliza como base:

```text
python:3.11-slim
```

e instala las dependencias desde el `requirements.txt` ubicado en la raíz.

La imagen puede construirse desde la raíz mediante:

```bash
docker build -f app/Dockerfile -t reactiva-local .
```

La aplicación dentro del contenedor se inicia mediante:

```text
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

El puerto expuesto es:

```text
8501
```

Una ejecución local utilizando variables de entorno externas puede realizarse mediante:

```bash
docker run --rm -p 8501:8501 --env-file .env reactiva-local
```

La aplicación queda disponible localmente en:

```text
http://localhost:8501
```

Las variables privadas y credenciales deben proporcionarse al contenedor de forma externa y nunca incorporarse dentro de la imagen Docker.

## Validaciones y pruebas

El proyecto cuenta con pruebas automáticas dentro de:

```text
tests/
```

Actualmente existen validaciones relacionadas con:

- preparación de datos;
- deduplicación;
- features;
- temporadas;
- grupos etarios;
- rankings contextuales;
- soporte mínimo;
- fallback;
- ausencia de productos repetidos.

También fueron realizadas validaciones sobre:

- imports del recomendador sin ejecuciones automáticas innecesarias;
- ejecución de notebooks desde un kernel limpio;
- consistencia de las features centralizadas;
- mantenimiento de la partición temporal;
- métricas de comparación;
- análisis de factibilidad;
- dependencias mediante `python -m pip check`;
- dependencias de AWS;
- Optuna;
- construcción de la imagen Docker;
- ejecución del contenedor;
- funcionamiento de Streamlit sobre el puerto 8501.

La cobertura de pruebas continuará ampliándose durante la integración final del pipeline y las funcionalidades pendientes.

## Componentes pendientes

El proyecto se encuentra en una etapa de integración y cierre, por lo que los principales puntos pendientes se concentran en finalizar y conectar componentes existentes.

Entre ellos:

- consolidación del ranking final de reactivación;
- separación entre recomendaciones de alta afinidad y oportunidades comerciales;
- reglas de exclusión y trazabilidad final del ranking;
- automatización del flujo de reactivación;
- generación de mensajes de contacto asociados a las recomendaciones;
- registro del histórico de acciones de reactivación;
- monitoreo de calidad de datos, categorías nuevas y drift;
- integración del pipeline completo end-to-end;
- pruebas de integración y automatización;
- ampliación del dashboard de Power BI;
- integración de outputs de reactivación con Power BI;
- documentación final;
- prueba end-to-end externa;
- preparación de Demo 2 y release final.

La implementación definitiva de estos componentes debe realizarse mediante las Issues correspondientes y el flujo de revisión establecido por el equipo.

## Alcance fuera del MVP

Actualmente quedan fuera del alcance obligatorio del MVP:

- modelo binario de probabilidad de recompra;
- target supervisado de recompra;
- API REST independiente;
- extensiones experimentales que no aporten valor directo a la solución final.

Estas decisiones buscan mantener el proyecto alineado con el problema de negocio y evitar agregar complejidad sin una necesidad funcional concreta.

Una funcionalidad excluida del MVP puede retomarse en una evolución futura si aparece evidencia o una necesidad de producto que lo justifique.

## Solución de problemas

Los problemas técnicos confirmados durante el desarrollo, junto con su causa, solución, resultado y medidas de prevención, se documentan en:

[`docs/troubleshooting/README.md`](docs/troubleshooting/README.md)

Cada incidencia documentada debe incluir, cuando corresponda:

- contexto;
- problema detectado;
- causa;
- solución aplicada;
- resultado;
- medidas de prevención.

Entre los problemas ya identificados durante el desarrollo se encuentran situaciones relacionadas con:

- reutilización incorrecta de ramas de trabajo;
- actualización y compatibilidad del dataset almacenado en S3;
- deduplicación incorrecta de transacciones legítimas;
- codificación del archivo `requirements.txt`;
- compatibilidad de dependencias de AWS;
- duplicación de archivos de dependencias;
- duplicación de implementaciones del recomendador;
- diferencias históricas entre la arquitectura inicialmente planificada y la arquitectura final basada en Streamlit;
- centralización del código reutilizado por Docker, Streamlit y los módulos internos.

La documentación de troubleshooting complementa al README principal: el README describe el estado y funcionamiento general del proyecto, mientras que `docs/troubleshooting/README.md` conserva el historial técnico de problemas confirmados y sus soluciones.
