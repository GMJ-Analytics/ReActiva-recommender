# ReActiva Recommender

Proyecto Final de Data Science desarrollado por **GMJ Analytics**.

## Objetivo

Desarrollar un sistema inteligente de recomendación y reactivación comercial que permita:

- Identificar clientes que alcanzan el criterio operativo de inactividad definido por el proyecto.
- Generar recomendaciones de productos orientadas a la reactivación de clientes inactivos.
- Generar recomendaciones comerciales para clientes que realizan compras en tiendas físicas.
- Resolver escenarios de cold start para clientes nuevos mediante similitud entre productos.
- Incorporar contexto estacional y geográfico cuando corresponda.
- Convertir los resultados en acciones comerciales concretas.
- Mantener una arquitectura preparada para integrar ventas provenientes de canales offline y online.

El planteo inicial del proyecto contemplaba estimar la probabilidad de recompra dentro de 180 días. A medida que evolucionó la solución, el alcance fue redefinido hacia un sistema de recomendación y reactivación basado actualmente en un criterio operativo de **270 días de inactividad**.

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
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
             EDA        Modelado temporal   Streamlit
                              │               │
                              │               ├── Cliente existente
                              │               │   → similitud cliente-cliente
                              │               │
                              │               ├── Cliente nuevo
                              │               │   → Item-to-Item
                              │               │
                              │               └── registro de ventas
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

La ingesta operativa de nuevas transacciones se mantiene separada del dataset canónico:

```text
Ventas offline
    │
    ▼
Streamlit
    │
    ▼
staging/individual/
```

y:

```text
Ventas online
    │
    ▼
Carga masiva simulada
    │
    ▼
staging/batch/
```

La consolidación nocturna será responsable de integrar ambos orígenes al dataset histórico canónico.

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

La estrategia de deduplicación incorpora:

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

Los enfoques actualmente evaluados incluyen:

- Gradient Boosting;
- Content-Based Recommendation;
- User-Based Collaborative Filtering;
- Popularity Baseline.

El enfoque Item-to-Item se mantiene como funcionalidad de recomendación basada en similitud de productos para determinados escenarios de Streamlit, pero no forma parte del conjunto principal de modelos comparados en el notebook final.

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

El modelo de Gradient Boosting cumple una responsabilidad diferente de la recomendación utilizada en el punto de venta.

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

Actualmente conviven tres mecanismos con responsabilidades distintas.

#### Reactivación de clientes inactivos

Para clientes que cumplen el criterio de inactividad se utiliza:

```text
Gradient Boosting
```

El modelo utiliza features históricas para predecir una categoría de interés y generar recomendaciones orientadas a reactivación.

#### Cliente existente en tienda física

Para un cliente que ya posee historial y realiza una nueva compra presencial, Streamlit utiliza una matriz cliente-producto y similitud coseno entre clientes.

Las funciones reutilizadas son:

```python
build_customer_profile()
build_customer_similarity()
```

El flujo general es:

```text
historial cliente-producto
        │
        ▼
similitud cliente-cliente
        │
        ▼
clientes similares
        │
        ▼
afinidad de productos
        │
        ├── Top 3 alta afinidad
        │
        └── hasta Top 3 oportunidad
```

Las recomendaciones de oportunidad utilizan productos con afinidad positiva, excluyen los productos ya seleccionados como Top de afinidad y priorizan menor rotación global, utilizando la afinidad como criterio secundario.

Este mecanismo es independiente del Gradient Boosting utilizado para reactivación.

#### Cliente nuevo sin historial

Para un cliente nuevo no existe todavía historial suficiente para aplicar similitud cliente-cliente.

En ese caso se utiliza recomendación:

```text
Item-to-Item
```

a partir del producto que el cliente está comprando.

La función utilizada es:

```python
get_recommendations_items()
```

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

### Cobertura funcional

Durante etapas anteriores de validación del recomendador basado en User-Based Collaborative Filtering se identificaron:

```text
1.028 clientes inactivos
```

y el flujo de recomendación utilizado en esa instancia consiguió obtener recomendaciones para todos ellos:

```text
0 clientes sin recomendación
```

Este resultado corresponde a una validación histórica de cobertura funcional del enfoque utilizado en esa etapa y no debe interpretarse como métrica del Gradient Boosting actualmente utilizado para reactivación.

Tampoco debe interpretarse como efectividad comercial real ni como garantía de que cada recomendación produzca una compra.

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

La indexación individual representa principalmente el flujo de atención de una venta realizada desde una tienda física.

La aplicación permite trabajar con:

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

Cada nueva transacción recibe inmediatamente un:

```text
Transaction ID
```

único basado en UUID.

Esto permite diferenciar cada operación sin depender de un identificador secuencial compartido entre distintas sucursales o instancias de la aplicación.

### Identificación de clientes existentes

Para un cliente existente, Streamlit permite seleccionar el nombre registrado y mostrar los datos conocidos del cliente.

El correo electrónico actúa como dato adicional de confirmación.

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

Esto evita que dos sucursales o instancias de Streamlit intenten generar simultáneamente el mismo siguiente identificador secuencial.

La asignación definitiva del cliente queda reservada al proceso de consolidación.

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

Si no existe coincidencia con un cliente registrado, se asignará un nuevo:

```text
CUSTXXXXXX
```

correlativo durante la consolidación.

Si el email coincide pero el nombre no coincide, el registro no debe fusionarse automáticamente sin control, ya que podría representar un conflicto de identidad.

El `Transaction ID` es independiente de este proceso y permanece único desde el momento en que se registra la venta.

### Persistencia de ventas offline

Las transacciones individuales se almacenan como objetos independientes dentro de:

```text
staging/individual/
```

Cada venta se guarda de forma independiente.

Esto evita que dos sucursales o usuarios modifiquen simultáneamente un mismo archivo compartido.

El flujo es:

```text
venta offline
      │
      ▼
Streamlit
      │
      ▼
validación
      │
      ▼
Transaction ID único
      │
      ▼
staging/individual/
```

### Carga masiva

La carga masiva representa principalmente la ingesta simulada de ventas provenientes del canal online.

El proyecto todavía no dispone de integración directa con un e-commerce real, por lo que este origen se representa mediante archivos CSV.

El flujo actual permite:

```text
archivo CSV
    │
    ▼
validación previa
    │
    ▼
DataValidator
    │
    ▼
limpieza
    │
    ▼
staging/batch/
```

Las cargas masivas se almacenan en:

```text
staging/batch/
```

diferenciándolas de las ventas individuales realizadas desde tienda física.

### Validación preventiva de archivos masivos

Antes de que Pandas procese una carga masiva se valida que el archivo:

- no esté vacío;
- no supere el tamaño máximo operativo definido por la aplicación.

El límite actualmente definido es:

```text
20 MB
```
l mismo límite se encuentra configurado a nivel de Streamlit mediante:

```text
.streamlit/config.toml

[server]
maxUploadSize = 20

Después de esta validación previa se ejecutan los controles existentes de `DataValidator`, incluyendo controles de esquema, columnas, valores faltantes, tipos, duplicados, fechas, identificadores y otras reglas de calidad.

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
    ├── ventas offline → staging/individual/
    │
    └── ventas online  → staging/batch/
    │
    ▼
consolidación nocturna
    │
    ▼
dataset canónico actualizado
    │
    ▼
recomendaciones del día siguiente
```

La incorporación de transacciones en tiempo real o casi real puede considerarse una mejora futura si el volumen o el caso de negocio lo requieren.

### Consolidación nocturna

La consolidación nocturna se encuentra definida como componente de integración entre staging y el dataset canónico.

La lógica objetivo contempla:

```text
leer staging/
→ validar archivos
→ descartar o ignorar Transaction ID ya procesados
→ consolidar transacciones
→ resolver PENDING
→ asignar CUSTXXXXXX cuando corresponda
→ actualizar dataset canónico
→ confirmar escritura exitosa
→ mover o borrar staging procesado
→ registrar logs y errores
```

La ejecución automática de esta consolidación forma parte de la arquitectura prevista y debe integrarse mediante la infraestructura correspondiente.

Los archivos de staging solamente deben eliminarse o archivarse después de confirmar que la actualización del dataset canónico finalizó correctamente.

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

### Auditoría y logs

La cuarta pestaña está disponible para usuarios con rol administrativo.

Permite visualizar archivos de log estructurados y filtrar registros por nivel.

La lectura de logs contempla además registros donde:

```text
level
```

pueda estar ausente o contener un valor nulo.

En esos casos se utiliza defensivamente:

```text
UNKNOWN
```

evitando que un registro histórico o externo con estructura incompleta interrumpa la visualización de la auditoría.

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
    └── cargas masivas
```

Cada archivo utiliza una key única basada en fecha, hora y un identificador aleatorio.

Esto reduce el riesgo de colisiones entre procesos concurrentes.

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

La imagen puede construirse desde la raíz del repositorio mediante:



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

## Validaciones y pruebas

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

### Validación funcional de Streamlit

El flujo de Streamlit fue validado funcionalmente con los tres escenarios principales.

#### Cliente existente

Se verificó:

```text
transacción válida
→ Transaction ID único
→ subida a staging/individual/
→ recomendación por similitud cliente-cliente
→ Top 3 alta afinidad
→ Top oportunidad
```

#### Cliente nuevo

Se verificó:

```text
transacción válida
→ PENDING-UUID
→ Transaction ID único
→ subida a staging/individual/
→ recomendación Item-to-Item
```

#### Carga masiva

Se verificó mediante un archivo de prueba de:

```text
3 filas
27 columnas
```

El flujo completó:

```text
lectura
→ validación
→ limpieza
→ 3 filas antes
→ 3 filas después
→ subida a staging/batch/
```

Los objetos utilizados exclusivamente para pruebas fueron eliminados posteriormente de staging para evitar que una futura consolidación los interprete como transacciones reales.

## Componentes pendientes

El repositorio también contiene componentes correspondientes a etapas que todavía deben continuar desarrollándose.

Entre los principales puntos pendientes se encuentran:

- consolidación nocturna productiva de `staging/individual/` y `staging/batch/`;
- resolución definitiva de identificadores `PENDING-UUID`;
- asignación segura de nuevos `CUSTXXXXXX`;
- idempotencia del proceso de consolidación mediante `Transaction ID`;
- automatización de la consolidación mediante infraestructura programada;
- sistema de mensajería para campañas de reactivación;
- automatización completa del pipeline;
- publicación y distribución definitiva del dashboard Power BI;
- integración de outputs procesados con BI;
- métricas y KPIs comerciales adicionales;
- trazabilidad comercial adicional;
- futura capa de API;
- actualización casi en tiempo real del recomendador como posible mejora de escalabilidad;
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

El criterio vigente del proyecto para considerar a un cliente inactivo es de **270 días**.

Este valor reemplaza el criterio anterior de 180 días mencionado en documentación histórica.

La evaluación actual de los modelos utiliza una separación temporal asociada a este criterio, evitando utilizar compras futuras durante la construcción de las recomendaciones.

El criterio debe diferenciarse de una garantía comercial: considerar un cliente inactivo según este corte constituye una regla operativa del proyecto y no implica afirmar que el cliente haya abandonado definitivamente la empresa.

## Decisión de consistencia temporal

La versión actual de ReActiva no requiere que una transacción realizada durante el día modifique inmediatamente las recomendaciones producidas ese mismo día.

El sistema trabaja con:

```text
dataset canónico consolidado
```

para construir recomendaciones.

Las nuevas ventas se almacenan primero en staging y serán incorporadas al dataset histórico durante el proceso de consolidación.

Por lo tanto:

```text
venta realizada hoy
→ staging
→ consolidación
→ dataset canónico actualizado
→ recomendador actualizado posteriormente
```

Esta decisión reduce complejidad, evita leer continuamente todos los objetos de staging y mantiene una arquitectura adecuada para el alcance actual del proyecto.

Una arquitectura de actualización en tiempo real o near-real-time puede implementarse en una futura evolución si el volumen o los requisitos del negocio lo justifican.

## Dashboard Power BI

El proyecto incluye un dashboard interactivo de EDA y calidad desarrollado en Power BI y versionado mediante Power BI Project (PBIP).

El proyecto se encuentra en:

```text
dashboard/ReActiva_EDA_Quality.pbip
```

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

```text
dashboard/data
```

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
- centralización del código utilizado por Docker y Streamlit;
- compatibilidad entre la evolución del modelo de reactivación y las recomendaciones utilizadas por Streamlit;
- control de cache del dataset histórico;
- separación de staging para ventas individuales y cargas masivas;
- validación preventiva de archivos antes de su procesamiento;
- robustez de la lectura de logs.

La documentación de troubleshooting complementa al README principal: el README describe el estado y funcionamiento general del proyecto, mientras que `docs/troubleshooting/README.md` conserva el historial técnico de problemas confirmados y sus soluciones.