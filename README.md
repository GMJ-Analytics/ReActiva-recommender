# ReActiva Recommender

Proyecto Final de Data Science desarrollado por **GMJ Analytics**.

## Objetivo

Desarrollar un sistema inteligente que permita:

- Estimar la probabilidad de recompra de un cliente dentro de 180 días.
- Identificar clientes con riesgo de no volver a comprar.
- Generar un ranking Top 5 de productos recomendados.
- Incorporar contexto estacional y geográfico.
- Convertir los resultados en acciones comerciales concretas.

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

Proyecto en etapa inicial de configuración y preparación del repositorio.

pyproject.toml > archivo para la instalación del module reactivate |

                                                         |_ una vez se decarguen los archivos en local ejecutar en la terminar pip install e . esto permitira importar load_data.py desde cualquier lugar del proyecto debido a que reactiva estará instaldo en el env

### Estado actual del desarrollo

Desde la creación de esta descripción inicial, el proyecto avanzó sobre la estructura base y actualmente cuenta con componentes funcionales de preparación de datos, análisis exploratorio, ingeniería de features, modelado, recomendación, validación, aplicación interactiva, almacenamiento en AWS S3, logging estructurado, pruebas automáticas y ejecución mediante Docker.

El archivo `pyproject.toml` continúa siendo utilizado para definir el paquete `reactiva` bajo la estructura `src/`.

La instalación editable utilizada actualmente puede realizarse desde la raíz del repositorio mediante:

```bash
python -m pip install -e .
```

Esto permite importar los módulos del paquete `reactiva` desde distintos componentes del proyecto sin depender de rutas manuales.

Por ejemplo:

```python
from reactiva.data.load_data import load_data
```

La lógica reutilizable del proyecto se encuentra centralizada principalmente en:

```text
src/reactiva/
```

evitando, cuando es posible, mantener implementaciones duplicadas entre notebooks, Streamlit y los módulos productivos.

### Arquitectura actual del repositorio

La estructura principal del proyecto es actualmente:

```text
ReActiva-recommender/
│
├── .github/
│
├── api/
│
├── app/
│   ├── app.py
│   └── Dockerfile
│
├── artifacts/
│
├── dashboard/
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

Algunas carpetas y archivos forman parte de la arquitectura objetivo del proyecto y todavía no contienen su implementación definitiva.

En particular, las áreas de API, Power BI, backtesting productivo y otros componentes del pipeline continúan desarrollándose mediante las Issues correspondientes.

### Flujo técnico actual

El flujo general implementado puede representarse de la siguiente manera:

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
Modelado y recomendación
        │
        ├── User-Based Collaborative Filtering
        ├── Frequency-weighted User-Based
        ├── Content-Based
        ├── Popularity
        ├── Item-Based Collaborative Filtering
        ├── Classification
        └── Hybrid
        │
        ▼
Contexto y mecanismos de fallback
        │
        ▼
Streamlit
        │
        ▼
Interacción comercial / CRM
        │
        ▼
Resultados, S3 y logging
```

### Fuente de datos

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

Actualmente se utilizan variables de entorno como:

```text
DATASET_URI
S3_BUCKET
MATRIX_URI
AWS_REGION
API_KEY
USUARIO_ADMIN
PASSWORD_ADMIN
```

Las credenciales, contraseñas, API keys, tokens y secretos no deben almacenarse directamente en el código ni versionarse en GitHub.

El archivo privado:

```text
.env
```

debe mantenerse fuera del repositorio.

### Auditoría del dataset

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

### Validación y preparación reproducible

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

La estrategia de deduplicación fue ajustada para incorporar:

```text
Transaction ID
```

como parte de la identificación de una operación.

Esto evita considerar erróneamente como duplicadas compras legítimas realizadas por un mismo cliente sobre un mismo producto y fecha.

La preparación actual conserva las 10.000 transacciones válidas del dataset.

### Análisis exploratorio de datos

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

### Análisis de factibilidad del recomendador

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

El catálogo actual utilizado en estos análisis contiene 24 productos.

### Construcción centralizada de features

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

#### season

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

#### age_group

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

### Uso de Location

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

### Modelado y comparación de recomendadores


Los modelos de recomendación se evalúan mediante un esquema temporal común.

La evaluación utiliza una separación temporal de **270 días**, donde:

* las compras anteriores al punto de corte se utilizan como información histórica para construir las recomendaciones;
* el período reciente se utiliza dentro de la lógica de recomendación cuando corresponde;
* las compras posteriores al corte se reservan como **holdout** para evaluar las recomendaciones.

De esta manera se evita utilizar información futura durante el entrenamiento o la generación de recomendaciones.

La pregunta común de evaluación es:

> **¿Puede la información disponible antes de que un cliente potencialmente inactivo regrese ayudar a predecir qué productos comprará posteriormente?**

Todos los modelos se evalúan comparando:

```text
Productos recomendados
        vs
Compras reales futuras
```

Los enfoques evaluados incluyen:

* Gradient Boosting;
* Content-Based Recommendation;
* User-Based Collaborative Filtering;
* Popularity Baseline.

El enfoque Item-Item puede mantenerse como funcionalidad de recomendación basada en similitud de productos, pero no se incluye dentro de los experimentos de aprendizaje comparativos, ya que no realiza un proceso de aprendizaje incremental sobre los datos históricos.

### Métricas de evaluación

La evaluación no se limita únicamente a Precision, Recall y Hit Rate.

Se utilizan las siguientes métricas:

* **Precision@K**: proporción de productos recomendados que fueron realmente comprados.

* **Recall@K**: proporción de las compras reales futuras del cliente que fueron recuperadas por la lista de recomendaciones.

* **Hit Rate@K**: indica si al menos uno de los productos recomendados fue comprado por el cliente.

* **NDCG@K**: evalúa la calidad del ranking y otorga mayor importancia a los productos relevantes que aparecen en posiciones superiores.

* **MAP@K**: evalúa la precisión en las posiciones donde aparecen productos relevantes dentro del ranking.

### Métricas Long-Tail

Para evaluar la capacidad de los modelos de recomendar productos menos frecuentes, se define el long-tail utilizando únicamente los datos de entrenamiento.

Los productos se ordenan según su frecuencia de compra y se utiliza un corte de **80% de participación acumulada de compras**. Los productos fuera de la parte principal de la distribución se consideran productos long-tail.

Las métricas adicionales son:

* **Long-tail Precision**: proporción de recomendaciones relevantes que pertenecen al long-tail.

* **Long-tail Recall**: proporción de productos long-tail realmente comprados que fueron recuperados por las recomendaciones.

* **Long-tail Hit Rate**: proporción de clientes para los cuales se recomendó al menos un producto long-tail relevante.

* **Long-tail Share**: proporción de posiciones de recomendación ocupadas por productos long-tail.

* **Long-tail Catalog Coverage**: proporción del catálogo long-tail disponible que aparece al menos una vez en las recomendaciones.

### Average Score y Sparsity

También se reportan:

* **Average Score**: media aritmética de:

  * Precision;
  * Recall;
  * Hit Rate;
  * Long-tail Precision;
  * Long-tail Recall;
  * Long-tail Hit Rate;
  * NDCG;
  * MAP.

**Long-tail Share**, **Long-tail Catalog Coverage** y **Sparsity** no se incluyen dentro del Average Score, ya que se utilizan como métricas de distribución, cobertura y características del sistema.

* **Sparsity**: mide la proporción de interacciones posibles cliente-producto que no contienen una compra.

Esto permite evaluar los modelos desde diferentes perspectivas y no únicamente por la cantidad de coincidencias entre productos recomendados y compras futuras.


### Optimización mediante Optuna

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

utilizado dentro del enfoque de clasificación.

La optimización mantiene:

- la misma ventana temporal;
- los mismos clientes evaluables;
- las mismas métricas principales utilizadas en la comparación de modelos.

La ejecución registrada utiliza 100 trials.

El mejor trial obtenido registró aproximadamente:

```text
Precision@5: 0.1135
Recall@5:    0.3512
HitRate@5:   0.4823
```

Los hiperparámetros encontrados pueden posteriormente compararse contra el modelo base utilizando el mismo marco de evaluación.

### Recomendador canónico

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

También se dispone de recomendación mediante similitud de productos a través de:

```python
get_recommendations_items()
```

utilizada actualmente por Streamlit.

La matriz de similitud de productos se carga cuando es requerida y puede mantenerse en memoria durante la ejecución, evitando realizar una carga automática innecesaria al importar el módulo.

### Contexto y fallback

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

El fallback puede completar progresivamente el Top K utilizando más de un nivel.

Los productos incorporados no se repiten.

La función contextual devuelve además información de trazabilidad que permite identificar:

- nivel evaluado;
- soporte disponible;
- si el nivel fue utilizado;
- motivo por el cual se utilizó o descartó;
- productos incorporados desde ese nivel.

Esta trazabilidad permite posteriormente explicar de qué forma se construyó una recomendación.

### Cobertura funcional del recomendador

Durante las validaciones realizadas sobre el criterio vigente de 270 días se identificaron:

```text
1.028 clientes inactivos
```

y el flujo de recomendación consiguió obtener recomendaciones para todos ellos:

```text
0 clientes sin recomendación
```

Este resultado representa una validación de cobertura funcional.

No debe interpretarse como efectividad comercial real ni como garantía de que cada recomendación vaya a producir una compra.

### Streamlit

La aplicación interactiva del proyecto se encuentra en:

```text
app/app.py
```

y está desarrollada utilizando:

```text
Streamlit
```

La aplicación funciona como interfaz de interacción con diferentes componentes de ReActiva.

Actualmente contiene áreas para:

1. Indexación individual.
2. Carga masiva.
3. Explorador 360 y CRM.
4. Auditoría y logs para usuarios con acceso administrativo.

#### Indexación individual

La aplicación permite trabajar tanto con:

- clientes existentes;
- perfiles nuevos sin historial.

Se solicitan datos relacionados con:

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

Para clientes sin historial, donde un recomendador colaborativo no dispone todavía de información individual suficiente, se utiliza una estrategia inicial de cold start basada en características contextuales disponibles.

#### Carga masiva

Streamlit permite trabajar con conjuntos de transacciones y aplicar controles de validación antes de continuar con el flujo.

Los datos pueden posteriormente almacenarse en S3 cuando la configuración y permisos disponibles lo permiten.

#### Explorador 360 y CRM

La aplicación dispone de una vista orientada al análisis individual de clientes.

Entre las métricas actualmente calculadas se encuentran:

- cantidad de compras;
- gasto total;
- ticket promedio;
- categoría más frecuente;
- marca más frecuente;
- ubicación;
- última compra;
- días de inactividad;
- historial de compras;
- nivel asociado al criterio de inactividad.

### Logging estructurado

El sistema de logging se encuentra implementado en:

```text
src/reactiva/utils/logger.py
```

Los registros se generan en formato JSON.

Actualmente pueden escribirse:

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

Cuando se detectan estos campos, su valor se reemplaza en los logs por:

```text
[REDACTED]
```

Esto reduce el riesgo de que credenciales o secretos aparezcan accidentalmente en registros del sistema.

### AWS S3

Amazon S3 forma parte de la arquitectura actual de ReActiva.

Se utiliza como fuente o destino para distintos elementos del proyecto, entre ellos:

- dataset histórico;
- resultados procesados;
- archivos generados;
- artefactos utilizados por componentes del recomendador.

La comunicación con AWS se realiza utilizando configuración y credenciales externas al código.

Las credenciales nunca deben incorporarse dentro de archivos versionados en GitHub.

### Dependencias

El archivo canónico de dependencias del proyecto es:

```text
requirements.txt
```

ubicado en la raíz del repositorio.

Se eliminaron listas de dependencias duplicadas para evitar diferencias entre componentes del proyecto.

Entre las principales tecnologías presentes actualmente se encuentran:

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
- python-dotenv;
- Uvicorn.

`Uvicorn` permanece como dependencia disponible para una futura implementación de API, pero actualmente no se utiliza para ejecutar `app.py`, ya que la aplicación existente está desarrollada con Streamlit.

### Instalación del entorno

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

### Ejecución de Streamlit

Con el entorno configurado y las variables necesarias disponibles:

```bash
streamlit run app/app.py
```

### Docker

El proyecto cuenta actualmente con una configuración funcional de Docker.

El archivo correspondiente se encuentra en:

```text
app/Dockerfile
```

La imagen utiliza como base:

```text
python:3.11-slim
```

e instala las dependencias desde el `requirements.txt` ubicado en la raíz.

La imagen puede construirse desde la raíz del repositorio mediante:

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

Una ejecución local utilizando variables de entorno externas puede realizarse, por ejemplo, mediante:

```bash
docker run --rm -p 8501:8501 --env-file .env reactiva-local
```

La aplicación queda disponible localmente en:

```text
http://localhost:8501
```

Las variables privadas y credenciales deben proporcionarse al contenedor de forma externa y nunca incorporarse dentro de la imagen Docker.

### Validaciones y pruebas

El proyecto cuenta con pruebas automáticas dentro de:

```text
tests/
```

Actualmente se validan componentes relacionados con:

- preparación de datos;
- deduplicación;
- features;
- temporadas;
- grupos etarios;
- rankings contextuales;
- soporte mínimo;
- fallback;
- ausencia de productos repetidos.

Después de la integración más reciente de features contextuales, recomendador y Docker, la suite completa registró:

```text
19 passed
```

También fueron validados:

- imports del recomendador sin ejecuciones automáticas;
- ejecución de notebooks desde un kernel limpio;
- consistencia de las features centralizadas;
- mantenimiento de la partición temporal;
- mantenimiento de las métricas de comparación;
- análisis de factibilidad después de la centralización de features;
- `python -m pip check`;
- dependencias de AWS;
- Optuna;
- construcción de la imagen Docker;
- ejecución del contenedor;
- funcionamiento de Streamlit sobre el puerto 8501.

### Componentes pendientes

El repositorio también contiene componentes correspondientes a etapas que todavía deben continuar desarrollándose.

Entre los principales puntos pendientes se encuentran:

- backtesting histórico reproducible;
- consolidación de tablas de resultados;
- modelo de datos para Power BI;
- dashboard de Power BI;
- métricas y KPIs comerciales;
- integración de outputs procesados con BI;
- evolución del ranking comercial;
- separación de recomendaciones de afinidad y oportunidades comerciales;
- trazabilidad comercial adicional;
- futura capa de API;
- integración final de los componentes dentro del pipeline completo.

La presencia de carpetas o archivos preparados para estas funciones no implica que dichas funcionalidades estén finalizadas.

Su implementación definitiva debe realizarse mediante las Issues correspondientes y el flujo de revisión establecido por el equipo.

## Actualización del dataset

El dataset actual incorpora los campos `Customer Full Name` y `Customer Email` para que el flujo de reactivación pueda identificar al cliente de forma legible y disponer de un medio de contacto.

Estos dos campos fueron incorporados de forma sintética con fines operativos del proyecto:

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

Esta modificación fue incorporada también a los procesos de auditoría, validación, preparación, documentación y análisis que consumen el dataset.

El diccionario de datos actualizado se encuentra disponible en:

[`docs/data_dictionary.csv`](docs/data_dictionary.csv)

Los campos `Customer Full Name` y `Customer Email` deben considerarse variables operativas incorporadas para hacer posible la representación del flujo de contacto con clientes y no variables originales obtenidas del dataset fuente.

## Criterio actual de inactividad

El criterio vigente del proyecto para considerar a un cliente inactivo es de **270 días**. Este valor reemplaza el criterio anterior de 180 días mencionado en documentación previa.

El criterio anterior se mantiene visible dentro de la documentación histórica y del objetivo original del proyecto para conservar la trazabilidad de la evolución de la solución.

La evaluación actual de los modelos utiliza además una separación temporal de 270 días, donde las compras del período final se reservan como holdout y la información anterior al corte se utiliza para construir las recomendaciones que luego son evaluadas.

De esta manera se evita utilizar información futura del período de evaluación durante la construcción de las recomendaciones.

El criterio debe diferenciarse de una garantía comercial: considerar un cliente inactivo según este corte constituye una regla operativa del proyecto y no implica afirmar que el cliente haya abandonado definitivamente la empresa.

## Dashboard Power BI

El proyecto incluye un dashboard interactivo de EDA y calidad desarrollado en Power BI y versionado mediante Power BI Project (PBIP).

El proyecto se encuentra en:

`dashboard/ReActiva_EDA_Quality.pbip`

Actualmente contiene dos páginas:

- `Resumen Ejecutivo`: KPIs generales, evolución temporal, distribución por categoría y canal, y métricas de calidad del dataset.
- `Análisis Comercial`: rankings de productos, marcas y ubicaciones, estado y rango etario de clientes, y comportamiento por método de pago.

### Generación de tablas para Power BI

Las tablas utilizadas por el dashboard se generan de forma reproducible mediante:

```bash
python -m reactiva.data.build_bi_eda_tables
```

El proceso crea o reemplaza los siguientes archivos en `dashboard/data/`:

- `bi_transactions.csv`
- `bi_customers.csv`
- `bi_products.csv`
- `bi_calendar.csv`
- `bi_quality_summary.csv`
- `bi_quality_columns.csv`

La generación reutiliza componentes canónicos del proyecto para validación y construcción de features, evitando duplicar lógica de negocio.

### Configuración local de la fuente

Las consultas de Power BI utilizan el parámetro `RutaDatosBI` como única ubicación base para los archivos CSV.

Al trabajar desde una nueva máquina o desde otra ubicación del repositorio, debe modificarse una sola vez este parámetro desde Power Query para que apunte a la carpeta local:

`dashboard/data`

Los archivos locales de caché y configuración de Power BI (`localSettings.json` y `cache.abf`) no se versionan.

La estrategia definitiva de publicación y distribución del dashboard se definirá separadamente de esta implementación local.

## Solución de problemas

Los problemas técnicos confirmados durante el desarrollo, junto con su causa, solución, resultado y medidas de prevención, se documentan en:

[`docs/troubleshooting/README.md`](docs/troubleshooting/README.md)

Este documento se utiliza para registrar incidencias técnicas reales detectadas durante el desarrollo y evitar que los mismos problemas vuelvan a repetirse.

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
- diferencias entre el runtime de Streamlit y una futura API;
- centralización del código utilizado por Docker y Streamlit.

La documentación de troubleshooting complementa al README principal: el README describe el estado y funcionamiento general del proyecto, mientras que `docs/troubleshooting/README.md` conserva el historial técnico de problemas confirmados y sus soluciones.

## Transaction Consolidator — AWS Lambda

The project includes an AWS Lambda component responsible for consolidating transaction files uploaded to the staging area in Amazon S3.

The Lambda source code is located in:

```text
artifacts/AwsLambda/lambda.py
```

The consolidator is designed to process CSV files stored under the configured staging prefix, combine them into a single consolidated transaction file, identify duplicate transactions, and generate an audit log for the records removed during deduplication.

### Consolidator flow

The implemented process follows this general flow:

```text
Streamlit / transaction source
          │
          ▼
       Amazon S3
          │
          ▼
   Staging transaction CSVs
          │
          ▼
   AWS Lambda Consolidator
          │
          ├── Read CSV files
          │
          ├── Validate schema
          │
          ├── Concatenate transactions
          │
          ├── Convert Purchase Date
          │
          ├── Detect duplicates
          │
          ├── Remove duplicates
          │
          ├── Write consolidated CSV
          │
          ├── Write duplicate audit
          │
          └── Remove processed staging files
          │
          ▼
Consolidated transaction dataset
```

### Main Lambda functions

The consolidator is organized around two main functions.

#### `read_csv_from_s3()`

```python
read_csv_from_s3(bucket, key)
```

This function reads an individual CSV object directly from Amazon S3.

The object is retrieved using `boto3`, decoded into text, and loaded into a pandas DataFrame.

This allows the Lambda to process the staging files without requiring them to be permanently downloaded to local storage.

#### `find_duplicates()`

```python
find_duplicates(df)
```

This function identifies duplicate transactions.

Transactions are grouped using the configured identity columns:

```text
Customer ID
session
Age
Gender
Location
Online/Offline
Category
Item Purchased
Brand
Color
Size
Quantity
Purchase Amount (₹)
Discount (%)
Festival/Sale
Subscription Status
Payment Method
Online Store
Shipping Charge (₹)
Delivery Speed
Delivery Time (Days)
```

Within each group, transactions are ordered by `Purchase Date`.

The consolidator uses a duplicate threshold of:

```text
2 seconds
```

When two otherwise identical transactions occur within two seconds, the oldest transaction is retained and the subsequent transaction is classified as a duplicate.

The function also creates audit information for every duplicate, including:

* duplicate transaction;
* reason for duplication;
* transaction ID that was retained;
* purchase date of the retained transaction;
* time difference between transactions;
* processing timestamp.

### `lambda_handler()`

```python
lambda_handler(event, context)
```

This is the Lambda entry point.

The function performs the complete consolidation workflow:

1. Lists CSV files in the staging S3 prefix.
2. Reads each CSV file.
3. Validates that all expected columns are present.
4. Concatenates the individual DataFrames.
5. Converts `Purchase Date` to a datetime value.
6. Validates that purchase dates are valid.
7. Calls `find_duplicates()`.
8. Removes the detected duplicate transactions.
9. Writes the consolidated dataset to the configured output key.
10. Generates a duplicate audit CSV when duplicates are detected.
11. Removes the successfully processed staging CSV files.
12. Returns a summary containing the number of files processed and rows before and after deduplication.

### S3 organization

The Lambda reads transaction files from the staging area:

```text
staging/individual/transactions_clean_2026/08/
```

The consolidated output is written to:

```text
csv_transactions_consolidated/consolidated_transactions.csv
```

Duplicate records are preserved separately through an audit file under:

```text
duplicate_audit/2026/08/
```

The staging files are removed only after the consolidation process has successfully completed. The purpose is to avoid keeping individual transaction files after they have been incorporated into the consolidated dataset.

The staging prefix itself is not deleted; only the processed CSV objects are removed.

### Dockerized Lambda

The consolidator is packaged as a Docker container using the AWS Lambda Python base image.

The Dockerfile is located in:

```text
artifacts/AwsLambda/Dockerfile
```

The image uses:

```dockerfile
FROM public.ecr.aws/lambda/python:3.12
```

This base image already provides:

* Python 3.12;
* the AWS Lambda runtime;
* the Lambda container execution environment;
* AWS SDK components such as `boto3`.

Therefore, `boto3` does not need to be installed separately for this implementation.

The additional dependency required by the consolidator is pandas:

```dockerfile
RUN pip install --no-cache-dir pandas
```

The Lambda source code is copied into the Lambda task root:

```dockerfile
COPY lambda.py lambda.py
```

The Lambda entry point is configured using:

```dockerfile
CMD ["lambda.lambda_handler"]
```

Unlike the Streamlit Docker image, the Lambda image does not require `EXPOSE` or a Streamlit server port. The AWS Lambda runtime handles invocation of the function.

The resulting image contains the Lambda runtime, Python, pandas and its dependencies, and the consolidator source code.

### Building the Lambda image

The Docker image is built for the Lambda-compatible Linux AMD64 architecture.

The build uses:

```powershell
docker buildx build `
  --platform linux/amd64 `
  --provenance=false `
  -t consolidator:latest `
  --load `
  .
```

The `--platform linux/amd64` option ensures that the image is built for the required Linux architecture.

The `--provenance=false` option prevents Docker from attaching provenance metadata that can result in an unsupported image manifest for AWS Lambda.

The `--load` option loads the resulting image into the local Docker image store.

### Current architecture

The consolidator adds a serverless processing component to the existing S3-based architecture:

```text
Streamlit
    │
    │ transaction CSV
    ▼
Amazon S3
    │
    │ staging files
    ▼
AWS Lambda
Transaction Consolidator
    │
    ├── pandas
    ├── validation
    ├── concatenation
    ├── deduplication
    └── audit
    │
    ├───────────────► Consolidated CSV
    │                 Amazon S3
    │
    └───────────────► Duplicate Audit
                      Amazon S3