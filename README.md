# ReActiva Recommender

Proyecto Final de Data Science desarrollado por **GMJ Analytics**.

## Objetivo

Desarrollar un sistema inteligente de recomendación y reactivación comercial que permita:

- Identificar clientes que alcanzan el criterio operativo de inactividad definido por el proyecto.
- Generar recomendaciones de productos orientadas a la reactivación de clientes inactivos.
- Generar recomendaciones comerciales para clientes que realizan compras en tiendas físicas.
- Resolver escenarios de clientes nuevos y clientes existentes mediante similitud entre productos cuando realizan una compra local.
- Incorporar contexto estacional y geográfico cuando corresponda.
- Convertir los resultados en acciones comerciales concretas.
- Mantener una arquitectura preparada para integrar ventas provenientes de canales offline y online.

El planteo inicial del proyecto contemplaba estimar la probabilidad de recompra dentro de 180 días. A medida que evolucionó la solución, el alcance fue redefinido hacia un sistema de recomendación y reactivación basado actualmente en un criterio operativo de **270 días de inactividad**.

ReActiva no predice actualmente si un cliente va a recomprar. El flujo de reactivación parte del historial disponible, identifica clientes que cumplen el criterio operativo de inactividad y genera recomendaciones orientadas a recuperarlos.

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

El proyecto se encuentra en una etapa avanzada de desarrollo e integración funcional.

Actualmente dispone de componentes funcionales de preparación de datos, análisis exploratorio, ingeniería de features, modelado, recomendación, validación, aplicación interactiva, almacenamiento en AWS S3, logging estructurado, pruebas automáticas, dashboard Power BI y ejecución mediante Docker.

### Estado actual del desarrollo

El archivo `pyproject.toml` se utiliza para definir el paquete `reactiva` bajo la estructura `src/`.

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
│       │   ├── models_comparison_final_metrics.ipynb
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

En particular, las áreas de API, automatización completa del pipeline, mensajería de campañas y otros componentes continúan desarrollándose mediante las Issues correspondientes.

### Flujo técnico actual

El flujo general puede representarse actualmente de la siguiente manera:

```text
                         Dataset histórico canónico
                                   │
                                   ▼
                              Amazon S3
                                   │
                                   ▼
                           Carga y validación
                                   │
                                   ▼
                       Ingeniería de features
                                   │
                  ┌────────────────┼────────────────┐
                  │                │                │
                  ▼                ▼                ▼
                 EDA       Modelado temporal     Streamlit
                                   │                │
                                   │                ├── Cliente existente Offline
                                   │                │   → Item-to-Item
                                   │                │
                                   │                ├── Cliente nuevo Offline
                                   │                │   → Item-to-Item
                                   │                │
                                   │                └── Venta Online individual
                                   │                    → registro sin recomendación
                                   │
                                   ▼
                         Clientes inactivos
                            >= 270 días
                                   │
                                   ▼
                           Gradient Boosting
                                   │
                                   ▼
                    Recomendaciones de reactivación
```

Las responsabilidades actuales quedan separadas de la siguiente manera:

```text
cliente existente en venta Offline
→ producto que está comprando
→ Item-to-Item
→ recomendaciones
```

```text
cliente nuevo en venta Offline
→ producto que está comprando
→ Item-to-Item
→ recomendaciones
```

```text
cliente inactivo >= 270 días
→ Gradient Boosting
→ predicción de categoría
→ productos recientes/populares de esa categoría
→ recomendación de reactivación
```

```text
venta Online individual
→ registrar transacción
→ no generar recomendación en Streamlit
```

La similitud Customer-Customer / User-Based no forma parte del flujo productivo vigente de Streamlit.

La ingesta operativa de nuevas transacciones se mantiene separada del dataset canónico:

```text
Venta individual
Offline u Online
      │
      ▼
   Streamlit
      │
      ▼
staging/individual/
```

y:

```text
Ventas online masivas
        │
        ▼
Carga manual CSV
        │
        ▼
staging/batch/
```

La consolidación nocturna será responsable en una etapa posterior de integrar ambos orígenes al dataset histórico canónico.

La implementación del consolidador nocturno no forma parte del alcance actual del PR que incorpora estas correcciones.

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
- detección de duplicados;
- integridad de `Transaction ID`;
- validez del canal.

El esquema canónico vigente contiene **27 columnas**.

Respecto de la estructura anterior:

```text
Frequency of Purchases
```

fue eliminada, mientras que se incorporaron:

```text
Customer Full Name
Customer Email
```

La columna:

```text
session
```

no forma parte del esquema canónico del dataset.

Los strings vacíos utilizados en campos sujetos a validación se normalizan para que puedan tratarse correctamente como valores faltantes.

Las columnas numéricas son convertidas de forma controlada y los valores que no puedan interpretarse como números válidos no deben pasar silenciosamente por el proceso.

#### Identidad de transacciones

La identidad única de una operación es:

```text
Transaction ID
```

Por lo tanto:

- `Transaction ID` es obligatorio;
- un identificador vacío es inválido;
- un identificador repetido dentro de un lote es inválido;
- dos registros distintos no deben considerarse operaciones independientes si comparten el mismo `Transaction ID`;
- una colisión de `Transaction ID` no debe resolverse silenciosamente eliminando una de las filas.

Las compras legítimas de un mismo cliente sobre un mismo producto y fecha siguen siendo transacciones independientes siempre que posean diferentes `Transaction ID`.

La clave histórica del reporte:

```text
duplicate_key_rows
```

se conserva por compatibilidad con los consumidores existentes, pero representa actualmente duplicados de `Transaction ID`.

Los duplicados completamente idénticos pueden tratarse como duplicados exactos, pero un conflicto donde el mismo `Transaction ID` identifica registros diferentes debe considerarse un error de integridad.

#### Canal

La variable:

```text
Online/Offline
```

debe contener un valor válido del dominio definido por el sistema.

El canal no se completa silenciosamente utilizando la moda, porque modificarlo de esa manera podría cambiar el significado operativo de una transacción.

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

La evolución del modelo de Gradient Boosting incorpora además features agregadas a nivel cliente mediante la función:

```python
build_customer_features()
```

Estas features resumen comportamiento histórico del cliente para ser utilizadas por el modelo de reactivación.

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

Los modelos de recomendación se evalúan mediante un esquema temporal que evita utilizar información futura durante el entrenamiento o la construcción de recomendaciones.

La implementación más reciente se encuentra en:

```text
src/reactiva/modeling/models_comparison_final_metrics.ipynb
```

La evaluación utiliza una separación temporal asociada al criterio de **270 días**, diferenciando:

```text
df_train
→ información histórica

df_recent
→ ventana reciente previa a la evaluación

df_future
→ ground truth / holdout futuro
```

Las compras futuras utilizadas como verdad de evaluación no participan en la construcción de las recomendaciones.

La pregunta común de evaluación es:

> **¿Puede la información disponible antes de que un cliente potencialmente inactivo regrese ayudar a predecir qué productos comprará posteriormente?**

Todos los modelos se evalúan comparando:

```text
Productos recomendados
        vs
Compras reales futuras
```

Dentro de los notebooks de experimentación y comparación se han evaluado enfoques como:

- Gradient Boosting;
- Content-Based Recommendation;
- User-Based Collaborative Filtering;
- Popularity Baseline.

La presencia de User-Based Collaborative Filtering dentro de análisis o notebooks históricos corresponde a una etapa experimental de comparación.

**User-Based / Customer-Customer no forma parte del flujo productivo vigente de Streamlit y no debe interpretarse como un componente activo de la arquitectura actual.**

El enfoque Item-to-Item se utiliza actualmente en Streamlit para recomendaciones asociadas a ventas locales de clientes existentes y nuevos.

### Gradient Boosting para reactivación

El modelo actual orientado a clientes inactivos utiliza:

```text
GradientBoostingClassifier
```

El flujo general es:

```text
historial anterior
        │
        ▼
build_customer_features()
        │
        ▼
Gradient Boosting
        │
        ▼
predicción de categoría
        │
        ▼
productos recientes de esa categoría
        │
        ▼
recomendación de reactivación
```

Los clientes candidatos a reactivación son aquellos que poseen historial anterior pero no registran compras dentro de la ventana reciente utilizada para aplicar el criterio de inactividad.

El modelo de Gradient Boosting cumple una responsabilidad diferente de la recomendación Item-to-Item utilizada durante una venta local en Streamlit.

### Métricas de evaluación

La evaluación no se limita únicamente a Precision, Recall y Hit Rate.

Se utilizan las siguientes métricas:

- **Precision@K**: proporción de productos recomendados que fueron realmente comprados.
- **Recall@K**: proporción de las compras reales futuras del cliente que fueron recuperadas por la lista de recomendaciones.
- **Hit Rate@K**: indica si al menos uno de los productos recomendados fue comprado por el cliente.
- **NDCG@K**: evalúa la calidad del ranking y otorga mayor importancia a los productos relevantes que aparecen en posiciones superiores.
- **MAP@K**: evalúa la precisión en las posiciones donde aparecen productos relevantes dentro del ranking.

### Métricas Long-Tail

Para evaluar la capacidad de los modelos de recomendar productos menos frecuentes, se define el long-tail utilizando únicamente los datos de entrenamiento.

Los productos se ordenan según su frecuencia de compra y se utiliza un corte de **80% de participación acumulada de compras**. Los productos fuera de la parte principal de la distribución se consideran productos long-tail.

Las métricas adicionales son:

- **Long-tail Precision**: proporción de recomendaciones relevantes que pertenecen al long-tail.
- **Long-tail Recall**: proporción de productos long-tail realmente comprados que fueron recuperados por las recomendaciones.
- **Long-tail Hit Rate**: proporción de clientes para los cuales se recomendó al menos un producto long-tail relevante.
- **Long-tail Share**: proporción de posiciones de recomendación ocupadas por productos long-tail.
- **Long-tail Catalog Coverage**: proporción del catálogo long-tail disponible que aparece al menos una vez en las recomendaciones.

### Average Score y Sparsity

También se reportan:

- **Average Score**: media aritmética de:
  - Precision;
  - Recall;
  - Hit Rate;
  - Long-tail Precision;
  - Long-tail Recall;
  - Long-tail Hit Rate;
  - NDCG;
  - MAP.

**Long-tail Share**, **Long-tail Catalog Coverage** y **Sparsity** no se incluyen dentro del Average Score, ya que se utilizan como métricas de distribución, cobertura y características del sistema.

- **Sparsity**: mide la proporción de interacciones posibles cliente-producto que no contienen una compra.

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

La arquitectura vigente diferencia dos mecanismos de recomendación y un comportamiento adicional para operaciones Online.

#### Reactivación de clientes inactivos

Para clientes que cumplen el criterio de inactividad se utiliza:

```text
Gradient Boosting
```

El modelo utiliza features históricas para predecir una categoría de interés y generar recomendaciones orientadas a reactivación.

El flujo es:

```text
cliente inactivo >= 270 días
        │
        ▼
Gradient Boosting
        │
        ▼
predicción de categoría
        │
        ▼
productos recientes/populares
de la categoría predicha
        │
        ▼
recomendaciones de reactivación
```

La implementación existente del Gradient Boosting se mantiene separada del flujo de recomendación utilizado durante una venta local.

#### Cliente existente en venta Offline

Para un cliente que ya posee historial y realiza una compra local, la recomendación parte del producto que está comprando.

Se utiliza:

```text
Item-to-Item
```

mediante la función:

```python
get_recommendations_items()
```

El flujo es:

```text
producto comprado actualmente
        │
        ▼
matriz de similitud entre productos
        │
        ▼
productos con similitud positiva
        │
        ▼
Top de recomendaciones
```

No se utiliza similitud Customer-Customer para este flujo.

#### Cliente nuevo en venta Offline

Para un cliente nuevo tampoco se intenta generar similitud entre clientes.

La recomendación utiliza igualmente:

```text
Item-to-Item
```

a partir del producto que se encuentra comprando.

Esto permite aplicar el mismo mecanismo basado en producto sin requerir historial previo del cliente.

#### Operaciones Online

Una transacción individual con canal:

```text
Online
```

se registra en el sistema, pero:

```text
NO genera recomendación en Streamlit
```

Las ventas online masivas se incorporan manualmente mediante el flujo CSV de `staging/batch/` mientras no exista una integración directa con el e-commerce.

#### Customer-Customer / User-Based

La similitud entre clientes quedó obsoleta para el flujo operativo vigente.

No se utiliza actualmente:

```text
build_customer_similarity()
```

ni una matriz de `cosine_similarity` entre clientes para generar las recomendaciones de Streamlit.

Las referencias a User-Based que permanezcan en notebooks corresponden a experimentación o evaluación histórica y no deben confundirse con la arquitectura productiva actual.

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

### Cobertura funcional histórica

Durante etapas anteriores de validación del recomendador basado en User-Based Collaborative Filtering se identificaron:

```text
1.028 clientes inactivos
```

y el flujo utilizado en esa instancia consiguió obtener recomendaciones para todos ellos:

```text
0 clientes sin recomendación
```

Este resultado corresponde exclusivamente a una validación histórica de un enfoque experimental anterior.

**User-Based Collaborative Filtering ya no forma parte del flujo productivo vigente.**

El resultado tampoco debe interpretarse como:

- métrica del Gradient Boosting actualmente utilizado para reactivación;
- efectividad comercial real;
- garantía de que una recomendación produzca una compra.

## Streamlit

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

### Indexación individual

La indexación individual permite registrar una nueva transacción desde Streamlit.

Puede trabajar con:

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

El canal no se ingresa como texto libre arbitrario, sino que debe corresponder a uno de los valores admitidos por el flujo.

El producto utilizado como disparador de una recomendación Item-to-Item debe existir dentro del catálogo soportado por el recomendador.

Cada operación genera un:

```text
Transaction ID
```

único basado en UUID.

El `Transaction ID` se mantiene estable durante la operación activa.

Un rerun de Streamlit o una segunda evaluación de la misma operación no debe generar silenciosamente una nueva identidad transaccional.

Después de completarse correctamente una operación, una nueva venta puede iniciar con nuevos identificadores.

### Identificación de clientes existentes

Para un cliente existente, Streamlit permite seleccionar el nombre registrado.

El nombre no se utiliza como identificador único de la persona.

El flujo es:

```text
Customer Full Name
        │
        ▼
buscar Customer ID asociados
        │
        ├── un único Customer ID
        │       → utilizar ese cliente
        │
        └── varios Customer ID
                → vendedor debe seleccionar
                  el Customer ID exacto
```

No se utiliza silenciosamente la primera fila disponible para decidir la identidad de un cliente.

Una vez seleccionado el `Customer ID`, la aplicación muestra los datos conocidos del perfil.

Para los campos históricos:

```text
Age
Gender
Location
Customer Email
```

se utiliza el valor válido más reciente disponible.

Si durante el historial aparecen distintos valores válidos para un mismo campo, la aplicación puede advertir esa inconsistencia en lugar de ocultarla.

El correo electrónico actúa además como dato de confirmación de identidad.

Si los datos corresponden al cliente identificado, se conserva su:

```text
Customer ID = CUSTXXXXXX
```

Si el cliente debe considerarse nuevo, se utiliza el flujo de perfil nuevo.

### Clientes nuevos y PENDING-UUID

Los clientes nuevos no reciben inmediatamente un `Customer ID` secuencial definitivo.

Durante la operación se genera:

```text
PENDING-UUID
```

El identificador `PENDING` se mantiene estable durante toda la operación activa.

No debe regenerarse en cada rerun de Streamlit.

Esto evita:

- crear varias identidades temporales para una misma operación;
- intentar generar identificadores secuenciales concurrentes desde distintas instancias;
- duplicar clientes por efectos propios del modelo de ejecución de Streamlit.

Los clientes nuevos deben ingresar un email con formato válido antes de completar la operación.

La asignación definitiva de un cliente queda reservada al futuro proceso de consolidación.

La regla objetivo de consolidación considera la normalización de:

```text
Customer Full Name
+
Customer Email
```

para resolver identidades.

El criterio previsto es:

```text
PENDING-UUID
        │
        ▼
normalizar nombre + email
        │
        ▼
¿nombre + email coinciden con cliente existente?
        │
       Sí
        │
        ▼
reutilizar CUST existente
```

Si no existe coincidencia con un cliente registrado, se podrá asignar un nuevo:

```text
CUSTXXXXXX
```

correlativo durante la consolidación.

Si el email coincide pero el nombre no coincide, el registro no debe fusionarse automáticamente sin control, ya que podría representar un conflicto de identidad.

El `Transaction ID` es independiente de este proceso y permanece único desde el momento en que se registra la venta.

**La transformación `PENDING-UUID → CUSTXXXXXX` no se implementa en el flujo actual de Streamlit ni forma parte del PR que incorpora estas correcciones.**

Su implementación corresponde a una Issue separada para el consolidador nocturno.

### Persistencia de ventas individuales

Las transacciones registradas individualmente desde Streamlit se almacenan como objetos independientes dentro de:

```text
staging/individual/
```

Esto aplica al mecanismo de venta individual.

Las operaciones Offline pueden generar recomendaciones Item-to-Item.

Las operaciones Online se registran, pero no generan recomendaciones en Streamlit.

Cada transacción individual se persiste de forma independiente.

El flujo general es:

```text
venta individual
      │
      ▼
Streamlit
      │
      ▼
validación
      │
      ▼
Transaction ID estable
      │
      ▼
staging/individual/
```

La operación incorpora controles destinados a evitar que un doble clic, un rerun o una segunda ejecución accidental registre la misma venta dos veces.

Entre las defensas utilizadas se encuentran:

- identidad transaccional estable durante la operación;
- control de segunda ejecución dentro de la sesión;
- persistencia idempotente;
- conservación del mismo `PENDING-UUID` cuando corresponde.

Una misma operación confirmada no debe generar dos transacciones distintas únicamente por ejecutarse nuevamente la interfaz.

### Carga masiva

La carga masiva representa el ingreso manual de ventas provenientes del e-commerce mientras el proyecto no disponga de una integración o API real con ese canal.

El formato operativo aceptado por este flujo es:

```text
CSV
```

No se mantiene una rama de lectura de Excel si el componente `file_uploader` solamente admite CSV.

El flujo actual es:

```text
archivo CSV
    │
    ▼
validación del archivo
    │
    ▼
validación transaccional
    │
    ▼
DataValidator
    │
    ▼
limpieza controlada
    │
    ▼
staging/batch/
```

Las cargas masivas se almacenan en:

```text
staging/batch/
```

diferenciándolas de las operaciones individuales de `staging/individual/`.

El batch debe representar ventas:

```text
Online
```

Un archivo con canal `Offline`, vacío o no reconocido no es válido para este flujo.

### Consistencia e idempotencia de la carga masiva

Antes de permitir la persistencia de un batch se controlan condiciones de integridad relacionadas con `Transaction ID`.

Entre ellas:

- `Transaction ID` debe existir;
- no puede estar vacío;
- no puede repetirse dentro del mismo archivo;
- no puede existir previamente en el dataset histórico canónico;
- todas las transacciones deben corresponder al canal `Online`.

Un batch que no supere estas validaciones debe rechazarse antes de su escritura en S3.

La repetición del mismo archivo dentro del flujo activo debe detectarse para evitar procesar y persistir dos veces un lote idéntico.

La aplicación mantiene asociada la validación al archivo efectivamente cargado.

Por lo tanto, si el usuario cambia el archivo seleccionado:

```text
archivo A validado
        │
        ▼
usuario selecciona archivo B
        │
        ▼
resultado limpio de A deja de ser válido
        │
        ▼
B debe validarse nuevamente
```

Esto evita reutilizar accidentalmente un `df_clean` perteneciente a un archivo anterior.

La comprobación global contra todos los objetos existentes en:

```text
staging/individual/
staging/batch/
```

no forma parte de esta etapa.

La reconciliación global de staging pertenece al futuro proceso de consolidación nocturna.

### Validación preventiva de archivos masivos

Antes de que Pandas procese una carga masiva se valida que el archivo:

- no esté vacío;
- no supere el tamaño máximo operativo definido por la aplicación.

El límite actualmente definido es:

```text
20 MB
```

El mismo límite se encuentra configurado a nivel de Streamlit mediante:

```text
.streamlit/config.toml
```

con:

```toml
[server]
maxUploadSize = 20
```

Después de esta validación previa se ejecutan los controles de `DataValidator`, incluyendo controles de:

- esquema;
- columnas;
- valores faltantes;
- tipos;
- identificadores;
- duplicados;
- fechas;
- rangos;
- canal;
- reglas de calidad.

La validación de tamaño no reemplaza al proceso de validación de datos; actúa como una protección previa antes de cargar archivos potencialmente demasiado grandes en memoria.

### Staging y consistencia diaria

Las nuevas ventas no se escriben directamente sobre el dataset histórico canónico.

La arquitectura utiliza:

```text
staging/individual/
staging/batch/
```

como capa de entrada.

La versión actual adopta un modelo de consistencia diaria.

Esto significa que las transacciones registradas durante el día:

```text
NO modifican inmediatamente las recomendaciones
```

generadas a partir del dataset canónico.

El flujo previsto es:

```text
durante el día
      │
      ├── ventas individuales
      │       → staging/individual/
      │
      └── ventas online masivas
              → staging/batch/
      │
      ▼
consolidación nocturna futura
      │
      ▼
dataset canónico actualizado
      │
      ▼
recomendaciones posteriores
```

La incorporación de transacciones en tiempo real o casi real puede considerarse una mejora futura si el volumen o el caso de negocio lo requiere.

### Consolidación nocturna

La consolidación nocturna está definida como un componente futuro de integración entre staging y el dataset canónico.

**Actualmente no se encuentra implementada y no forma parte del PR que incorpora las correcciones del flujo de Streamlit.**

La lógica objetivo contempla:

```text
leer staging/
→ validar archivos
→ reconciliar Transaction ID
→ evitar reprocesar operaciones ya consolidadas
→ consolidar transacciones
→ resolver PENDING
→ asignar CUSTXXXXXX cuando corresponda
→ actualizar dataset canónico
→ confirmar escritura exitosa
→ mover o borrar staging procesado
→ registrar logs y errores
```

También será responsabilidad de este proceso realizar controles globales entre el dataset canónico y los diferentes objetos acumulados en staging.

Los archivos de staging solamente deberán eliminarse o archivarse después de confirmar que la actualización del dataset canónico finalizó correctamente.

### Dataset canónico y cache

Streamlit utiliza el dataset histórico configurado mediante:

```text
DATASET_URI
```

como fuente canónica de información.

La carga utiliza cache de Streamlit con tiempo de vida controlado:

```python
@st.cache_data(ttl=3600)
```

De esta forma se evita releer innecesariamente el dataset desde S3 en cada interacción de la interfaz.

El cache tiene actualmente un TTL de:

```text
3600 segundos
```

equivalente a una hora.

La existencia de este cache es coherente con la decisión de arquitectura actual de no incorporar al recomendador las transacciones del mismo día hasta que se ejecute la consolidación correspondiente.

Cuando el dataset canónico se actualiza en S3, debe tenerse en cuenta la existencia de este cache durante las pruebas y validaciones funcionales.

### Explorador 360 y CRM

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

El cálculo de métricas descriptivas debe tolerar perfiles donde campos como:

```text
Category
Brand
Location
```

no posean valores válidos disponibles, evitando asumir que siempre existirá un primer elemento para seleccionar.

### Auditoría y logs

La cuarta pestaña está disponible para usuarios con rol administrativo.

Permite visualizar archivos de log estructurados y filtrar registros por nivel.

La lectura de logs contempla registros donde:

```text
level
```

pueda estar ausente o contener un valor nulo.

En esos casos se utiliza defensivamente:

```text
UNKNOWN
```

evitando que un registro histórico o externo con estructura incompleta interrumpa la visualización de la auditoría.

La vista administrativa también aplica una lectura acotada para evitar intentar cargar indefinidamente en memoria archivos de log completos cuyo tamaño pueda crecer con el funcionamiento del sistema.

El objetivo del visor es permitir inspección operativa sin convertir la interfaz en un consumidor ilimitado de memoria.

## Logging estructurado

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

## AWS S3

Amazon S3 forma parte de la arquitectura actual de ReActiva.

Se utiliza como fuente o destino para distintos elementos del proyecto, entre ellos:

- dataset histórico canónico;
- staging de ventas individuales;
- staging de cargas masivas;
- resultados procesados;
- archivos generados;
- artefactos utilizados por componentes del recomendador.

La comunicación con AWS se realiza utilizando configuración y credenciales externas al código.

Las credenciales nunca deben incorporarse dentro de archivos versionados en GitHub.

### Estructura de staging

Actualmente se diferencian dos entradas operativas:

```text
staging/
│
├── individual/
│   └── transacciones registradas individualmente
│
└── batch/
    └── cargas masivas online
```

La persistencia debe conservar la identidad de cada operación y evitar que una segunda ejecución accidental genere otra copia lógica de la misma transacción o del mismo lote.

Para ventas individuales, la identidad se encuentra vinculada al `Transaction ID` estable de la operación.

Para cargas masivas, el flujo mantiene controles destinados a impedir el reprocesamiento del mismo lote dentro de la operación activa.

Esta estrategia permite combinar:

- separación entre fuentes;
- trazabilidad;
- prevención de colisiones;
- idempotencia frente a reintentos;
- futura consolidación controlada.

La reconciliación global de todos los objetos existentes en staging se realizará en el consolidador nocturno futuro y no forma parte del flujo actual.

## Dependencias

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

La aplicación queda disponible normalmente en:

```text
http://localhost:8501
```

## Docker

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

La configuración compartida de Streamlit ubicada en:

```text
.streamlit/config.toml
```

también se copia dentro de la imagen Docker mediante:

```dockerfile
COPY .streamlit ./.streamlit
```

Esto mantiene dentro del contenedor el mismo límite de carga de archivos de **20 MB** utilizado durante la ejecución local.

La construcción debe realizarse utilizando la raíz del repositorio como contexto, de manera que el Dockerfile pueda acceder a las dependencias y archivos de configuración requeridos.

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

### Amazon ECR

After building the image, it is tagged with the Amazon ECR repository URI:

```powershell
docker tag consolidator:latest \
856554457924.dkr.ecr.us-east-1.amazonaws.com/consolidator:latest
```

Docker is authenticated against Amazon ECR using:

```powershell
aws ecr get-login-password --region us-east-1 |
docker login --username AWS --password-stdin \
856554457924.dkr.ecr.us-east-1.amazonaws.com
```

The image can then be pushed to ECR:

```powershell
docker push \
856554457924.dkr.ecr.us-east-1.amazonaws.com/consolidator:latest
```

The ECR image is subsequently used as the container image for the AWS Lambda function.

### Local Lambda testing

The Lambda container can also be executed locally using Docker.

For example:

```powershell
docker run --rm -p 9000:8080 consolidator
```

The Lambda Runtime Interface provided by the AWS Lambda base image listens internally on port `8080`. Port `9000` is used on the local machine to access the container during testing.

A local invocation can be sent using:

```powershell
Invoke-RestMethod -Method Post `
  -Uri "http://localhost:9000/2015-03-31/functions/function/invocations" `
  -Body '{}'
```

This allows the Lambda function to be tested locally before deploying the container image to AWS.

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
```

This component separates transaction ingestion from transaction consolidation and provides an auditable mechanism for identifying and removing duplicate records
# Customer Identity Resolution & Transaction Consolidation

## Overview

Implemented and integrated a customer identity-resolution process into the transaction consolidator to ensure that transactions belonging to the same customer are associated with a persistent `Customer ID`.

The main objective is to prevent customer records from becoming fragmented when the same customer appears in different staging files with a temporary `PENDING-*` customer ID or with slightly different customer information.

The consolidation pipeline now follows this general process:

```text
Staging Transactions
        ↓
Validate transaction structure
        ↓
Convert Purchase Date
        ↓
Resolve Customer Identity
        ↓
Detect Duplicate Transactions
        ↓
Remove Duplicates
        ↓
Write Consolidated Transactions
        ↓
Update Customer Registry
        ↓
Write Identity/Duplicate Audit Logs
```

## Customer Identity Resolution

A persistent customer registry was introduced as a source of truth for previously identified customers.

The registry stores the core information required to identify a customer:

* Customer ID
* Customer Full Name
* Customer Email
* Customer Phone / normalized phone
* Age

When a transaction arrives with a `PENDING-*` Customer ID, the system attempts to resolve that transaction to an existing customer before creating a new customer ID.

### Identity matching strategy

Identity resolution uses a tiered approach:

1. **Exact email match**
2. If email does not provide a match, use:

   * Phone number
   * Full name
   * Age within the configured tolerance
3. If neither method produces a match, create a new persistent Customer ID.

The phone number is normalized before comparison so that formatting differences do not prevent a match.

For example:

```text
+91 79794369905
917974369905
91-7979-436-9905
```

can be normalized to the same numeric representation.

## Why Phone + Full Name + Age Are Used Together

Email was initially considered as an identity signal, but email by itself is not sufficiently reliable to guarantee customer continuity.

A customer may provide a different email address during a subsequent purchase. For example, a customer could purchase something and then return one or two hours later using a different email address.

If email were the only identity mechanism, the system could interpret that transaction as belonging to a new customer:

```text
Purchase 1
Customer ID → CUST001000
Email → customer@email.com

        ↓

Purchase 2
Email → another@email.com
        ↓

New Customer ID → CUST001001
```

The same real-world customer would then be represented by two different customer IDs.

This creates **customer identity fragmentation**.

Using:

```text
Phone + Full Name + Age
```

provides an additional validation layer that makes it possible to recognize the customer even when the email changes.

The intention is not to treat any individual attribute as sufficient identity proof. The combination provides a stronger identity signal.

## Why Not Use Phone Alone?

Phone number alone can also produce false matches because a phone number may potentially be shared or reused.

Likewise:

* Phone + name can still produce ambiguous matches.
* Name alone is clearly insufficient.
* Age alone is insufficient.
* Email alone can change between transactions.

The selected combination:

```text
Phone + Full Name + Age
```

therefore provides a more conservative automatic identity-resolution rule while still allowing returning customers to retain their existing Customer ID.

An age tolerance is also applied because customer demographic information may change or may be recorded slightly differently between transactions.

## Business Cost-Benefit Consideration

There is a trade-off between two possible errors:

### False merge

The system could theoretically merge two different people if they happen to have:

```text
Same phone
+
Same full name
+
Same age
```

This is considered a relatively rare scenario compared with the more common problem of the same customer appearing with inconsistent information across purchases.

If a false merge occurs, the identity-resolution audit log provides traceability so the decision can be investigated and corrected.

### False split

The opposite situation is creating a new Customer ID for an existing customer.

For example:

```text
Purchase #1 → CUST001000

Purchase #2 → CUST001001
```

even though both transactions belong to the same person.

This creates an ongoing business cost:

* Fragmented purchase history
* Incorrect customer lifetime history
* Weaker customer profiling
* Reduced personalization
* Less reliable recommendations
* Incorrect purchase-frequency calculations
* Fragmented loyalty information
* More duplicate customer records
* Additional reconciliation work later

Therefore, always creating a new customer ID whenever any customer attribute changes can be more damaging over time than allowing a controlled identity merge based on multiple identity signals.

The chosen approach accepts a small and manageable false-merge risk in order to reduce the recurring and structurally more damaging problem of customer-history fragmentation.

## Auditability

Identity-resolution decisions are recorded in an audit log.

For each resolved pending customer, the audit records information such as:

* Original pending transaction ID
* Resolved Customer ID
* Resolution type
* Matching signals used
* Resolution timestamp

For example:

```text
PENDING-XXXX
        ↓
CUST001000
        ↓
resolution = merged_existing
        ↓
match_signals = phone+name+age
```

This makes automatic identity resolution **traceable rather than silent**.

The system therefore does not simply overwrite customer IDs without an explanation of how the decision was reached.

## Duplicate Detection

Duplicate detection was also restored as part of the consolidation process.

Duplicate transactions are identified using the configured identity fields and purchase date.

Transactions with the same identity characteristics and a purchase-date difference of two seconds or less are treated as duplicates.

The oldest transaction is retained as the anchor transaction.

The duplicate transaction is removed from the consolidated dataset and recorded in the duplicate audit log.

The audit includes information such as:

* Duplicate transaction
* Transaction that was retained
* Purchase-date difference
* Duplicate reason
* Processing timestamp

## Important Processing Order

Customer identity resolution is intentionally performed **before duplicate detection**.

This is important because a transaction may arrive with a temporary `PENDING-*` Customer ID.

If duplicate detection happened first, two transactions belonging to the same customer could appear to have different identities:

```text
Transaction A
Customer ID = PENDING-AAA

Transaction B
Customer ID = PENDING-BBB
```

After identity resolution:

```text
Transaction A
Customer ID = CUST001000

Transaction B
Customer ID = CUST001000
```

The duplicate-detection stage can therefore operate on the resolved customer identity rather than temporary identifiers.

This makes the consolidation process more logically consistent:

```text
Resolve WHO the customer is
        ↓
Determine WHICH transactions are duplicates
```

rather than attempting to determine duplicates using unresolved customer identities.

## Customer Registry vs. Audit Log

The customer registry and audit logs serve different purposes.

### Customer Registry

The registry answers:

> **Who is this customer?**

It acts as the persistent reference used by future Lambda executions to resolve incoming customer identities.

### Identity Audit Log

The identity audit answers:

> **What decision did the system make when resolving this customer, and why?**

### Duplicate Audit Log

The duplicate audit answers:

> **Which transaction was removed as a duplicate, which transaction was retained, and why?**

This separation keeps the persistent customer identity data distinct from the historical processing logs.

## Result

The consolidation process now provides a persistent customer identity layer while preserving the complete transaction dataset.

The intended result is:

```text
                    CUSTOMER REGISTRY
                           │
                           │
                    Customer Identity
                           │
                           ▼
STAGING → IDENTITY RESOLUTION → DUPLICATE DETECTION
                                      │
                                      ▼
                           CLEAN TRANSACTIONS
                                      │
                                      ▼
                         CONSOLIDATED DATASET
```

This approach reduces customer identity fragmentation, preserves customer purchase history, supports downstream personalization/recommendation systems, and maintains auditability for both identity-resolution and duplicate-removal decisions.

