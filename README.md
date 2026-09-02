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

1\. Las tareas se seleccionan desde las Issues habilitadas en GitHub Project.

2\. Cada integrante se asigna la Issue que va a desarrollar.

3\. Antes de comenzar una nueva tarea se actualiza la rama `main` local.

4\. Cada Issue se desarrolla en una rama independiente creada a partir de `main`.

5\. Los cambios se registran mediante commits y se publican en la rama correspondiente.

6\. La integración a `main` se realiza exclusivamente mediante Pull Request.

7\. La rama `main` se encuentra configurada para impedir el merge de un Pull Request hasta contar con al menos una aprobación de revisión por parte de otro integrante del equipo. Esta regla aplica también cuando el autor del PR es quien posee permisos para realizar el merge.

8\. Una vez aprobado y mergeado el PR, la Issue asociada se considera finalizada.

Este flujo permite mantener la trazabilidad de las tareas, los aportes individuales y las revisiones realizadas por el equipo durante el desarrollo del proyecto.

## Estado

El proyecto se encuentra en una etapa avanzada de integración funcional de extremo a extremo.

Actualmente dispone de componentes funcionales de preparación y validación de datos, análisis exploratorio, ingeniería de features, modelado, recomendación, Streamlit, almacenamiento en Amazon S3, logging estructurado, Docker, campañas mensuales de reactivación con cupones y mensajería, componentes AWS Lambda, monitoreo de data drift con Evidently y un dashboard Power BI orientado a negocio, campañas y monitoreo.

La configuración sensible de infraestructura —credenciales, identidades de Amazon SES, URLs públicas y secretos de firma— se mantiene fuera del código y se administra mediante la configuración correspondiente en AWS.

### Demo interactiva de Streamlit

La aplicación operativa de ReActiva se encuentra disponible en:

👉 [Abrir ReActiva en Streamlit](http://54.198.111.83:8501/)

La configuración sensible de infraestructura —credenciales, identidades de Amazon SES, URLs públicas y secretos de firma— se mantiene fuera del código y se administra mediante la configuración correspondiente en AWS.

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

La estructura principal utilizada por el proyecto es:

```text
ReActiva-recommender/
│
├── .github/
├── .streamlit/
├── api/
├── app/
│   ├── app.py
│   └── Dockerfile
│
├── artifacts/
│   └── AwsLambda/
│       ├── Dockerfile
│       ├── lambda_consolidator.py
│       ├── monthly_campaign/
│       ├── campaign_sender/
│       ├── unsubscribe/
│       └── evidently_drift/
│
├── dashboard/
│   ├── ReActiva_EDA_Quality.pbip
│   └── data/
│
├── data/
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
├── scripts/
│   └── refresh_bi_data.py
│
├── src/
│   └── reactiva/
│       ├── config.py
│       ├── campaigns/
│       │   ├── campaign.py
│       │   ├── coupon_service.py
│       │   ├── coupons.py
│       │   ├── orchestrator.py
│       │   ├── send_service.py
│       │   ├── sender.py
│       │   ├── service.py
│       │   ├── status.py
│       │   └── storage.py
│       ├── data/
│       │   ├── audit_data.py
│       │   ├── load_data.py
│       │   ├── save_results.py
│       │   └── validate_data.py
│       ├── features/
│       │   ├── build_features.py
│       │   └── context.py
│       ├── modeling/
│       ├── monitoring/
│       │   ├── drift.py
│       │   └── run_drift_monitoring.py
│       ├── pipeline/
│       ├── recommender/
│       │   └── recommender.py
│       └── utils/
│
├── tests/
├── actualizar_dashboard.bat
├── .dockerignore
├── .gitignore
├── pyproject.toml
├── requirements.txt
└── README.md
```

La lógica reutilizable permanece centralizada dentro de `src/reactiva/`. La API no constituye actualmente el entrypoint operativo de la solución: la interacción de usuario se realiza mediante Streamlit, mientras que los procesos automáticos se desacoplan mediante S3 y AWS Lambda.

Los componentes de campañas, mensajería, baja y monitoreo mantienen separadas sus responsabilidades. La creación de campaña consume la salida vigente del recomendador; el `campaign_sender` no entrena Gradient Boosting, no genera recomendaciones y no crea una campaña nueva.

### Flujo técnico actual

El flujo general puede representarse actualmente de la siguiente manera:

```text
Dataset histórico canónico + transacciones operativas consolidadas
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
          ┌──────────────┼──────────────┐
          │              │              │
          ▼              ▼              ▼
         EDA      Modelado temporal   Streamlit
                         │              │
                         │              ├── Cliente existente Offline
                         │              │   → Item-to-Item
                         │              │
                         │              ├── Cliente nuevo Offline
                         │              │   → Item-to-Item
                         │              │
                         │              └── Venta Online individual
                         │                  → registro sin recomendación
                         │
                         ▼
                Clientes inactivos
                   >= 270 días
                         │
                         ▼
                 Gradient Boosting
                         │
                         ▼
          Recomendaciones mensuales
                         │
                         ▼
                Campaña REACTIVA
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
       Email personalizado      Cupón individual
       días 1 a 5, 09:00       10% / un solo uso
       hora de India           hasta fin de mes
             │                       │
             └───────────┬───────────┘
                         ▼
                 Compra / reactivación
                         │
                         ▼
               Actualización de estado
```

Las responsabilidades productivas se encuentran separadas:

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
→ Gradient Boosting mensual
→ predicción de categoría
→ productos recientes/populares de esa categoría
→ recomendaciones de reactivación
→ campaña mensual
```

```text
venta Online individual
→ registrar transacción
→ no generar recomendación en Streamlit
```

La similitud Customer-Customer / User-Based no forma parte del flujo productivo vigente de Streamlit.

La ingesta operativa de nuevas transacciones se mantiene separada del dataset histórico:

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

El consolidador AWS Lambda integra las transacciones de staging, resuelve identidad cuando corresponde, controla duplicados y genera el archivo operativo consolidado utilizado por los procesos posteriores.

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

El esquema canónico vigente contiene **28 columnas**.

Respecto de la estructura anterior:

```text

Frequency of Purchases

```

fue eliminada, mientras que se incorporaron:

```text

Customer Full Name

Customer Email

Customer Phone

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

### Métricas de cola larga (Long-Tail)

Para evaluar la capacidad de los modelos de recomendar productos menos frecuentes, se define el long-tail utilizando únicamente los datos de entrenamiento.

Los productos se ordenan según su frecuencia de compra y se utiliza un corte de **80% de participación acumulada de compras**. Los productos fuera de la parte principal de la distribución se consideran productos long-tail.

Las métricas adicionales son:

- **Long-tail Precision**: proporción de recomendaciones relevantes que pertenecen al long-tail.

- **Long-tail Recall**: proporción de productos long-tail realmente comprados que fueron recuperados por las recomendaciones.

- **Long-tail Hit Rate**: proporción de clientes para los cuales se recomendó al menos un producto long-tail relevante.

- **Long-tail Share**: proporción de posiciones de recomendación ocupadas por productos long-tail.

- **Long-tail Catalog Coverage**: proporción del catálogo long-tail disponible que aparece al menos una vez en las recomendaciones.

### Puntaje promedio y sparsity

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

Recall@5:    0.3512

HitRate@5:   0.4823

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

1\. popularidad global;

2\. popularidad por `season`;

3\. popularidad por `Location`;

4\. popularidad por interacción `season + Location`.

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

1\. Indexación individual.

2\. Carga masiva.

3\. Explorador 360 y CRM.

4\. Auditoría y logs para usuarios con acceso administrativo.

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

        │       → utilizar ese cliente

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

Los clientes nuevos no reciben inmediatamente un `Customer ID` secuencial definitivo desde Streamlit.

Durante la operación se genera:

```text
PENDING-UUID
```

El identificador temporal se mantiene estable durante toda la operación activa y no debe regenerarse en cada rerun de Streamlit.

Esto evita:

- crear varias identidades temporales para una misma operación;
- intentar generar identificadores secuenciales concurrentes desde distintas instancias;
- duplicar clientes por efectos propios del modelo de ejecución de Streamlit.

Los clientes nuevos deben ingresar los datos requeridos por el flujo antes de completar la operación.

La asignación del `Customer ID` persistente se realiza durante la consolidación. El consolidador intenta resolver el `PENDING-UUID` contra el registro de clientes utilizando las señales de identidad disponibles y las reglas definidas para el proyecto.

El consolidador vigente resuelve identidades temporales utilizando la combinación:

```text
Customer Phone normalizado
Customer Full Name
Age dentro de la tolerancia configurada
```

`Customer Email` se conserva como atributo del registro de cliente, pero la implementación actual del consolidador no lo utiliza como señal de matching. Esta decisión evita depender de una dirección de correo que puede cambiar entre compras.

Si el cliente puede asociarse de forma confiable con una identidad existente, se reutiliza su `Customer ID`. Si no existe una coincidencia válida, se asigna un nuevo identificador persistente con formato:

```text
CUSTXXXXXX
```

El `Transaction ID` es independiente de este proceso y permanece único desde el momento en que se registra la venta.

La resolución de identidad se audita para evitar modificaciones silenciosas y permitir revisar posteriormente qué señales llevaron a una asociación o a la creación de un nuevo cliente.

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

La reconciliación global de staging pertenece al proceso de consolidación nocturna.

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

como capa de entrada operativa.

La versión actual adopta un modelo de consistencia diaria. Las transacciones registradas durante el día se almacenan en staging y son integradas por el proceso de consolidación antes de formar parte del conjunto operativo consolidado utilizado por los procesos posteriores.

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
consolidación
      │
      ▼
transacciones consolidadas
      │
      ▼
procesos posteriores y futuras ejecuciones
```

La arquitectura actual adopta consistencia diaria para las transacciones operativas; una integración en tiempo real permanece fuera del alcance vigente.

### Consolidación nocturna

La consolidación se implementa mediante un componente AWS Lambda ubicado en:

```text
artifacts/AwsLambda/lambda_consolidator.py
```

El proceso se encarga de integrar archivos operativos de staging y mantener trazabilidad de la consolidación.

Entre sus responsabilidades se encuentran:

```text
leer staging/
→ validar archivos
→ resolver identidad de clientes temporales
→ reconciliar Transaction ID
→ detectar duplicados
→ consolidar transacciones
→ actualizar el registro de clientes
→ escribir dataset consolidado
→ generar auditorías
→ eliminar archivos procesados solamente después de una escritura exitosa
→ registrar errores
```

La resolución de identidad se ejecuta antes de la detección de duplicados para que las transacciones se comparen utilizando la identidad persistente del cliente cuando sea posible.

Los archivos de staging solamente deben eliminarse después de confirmar que el proceso de consolidación y las escrituras correspondientes finalizaron correctamente.

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

## Registro estructurado (logging)

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

│   └── transacciones registradas individualmente

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

- consolidación controlada.

La reconciliación de los objetos de staging corresponde al proceso de consolidación y se mantiene separada del flujo interactivo de Streamlit.

## Servicio de campañas y mensajería de reactivación

ReActiva incorpora un subsistema mensual que transforma las recomendaciones para clientes inactivos en acciones comerciales trazables.

La lógica reutilizable se encuentra en:

```text
src/reactiva/campaigns/
```

Este subsistema se mantiene separado del recomendador Item-to-Item utilizado durante ventas Offline y también se mantiene separado del proceso mensual que genera las recomendaciones de reactivación.

La separación de responsabilidades es intencional:

```text
Recomendador mensual
        ↓
archivo canónico de recomendaciones
        ↓
creación de campaña
        ↓
campaign_active.csv
        ↓
campaign_sender
        ↓
Amazon SES
```

El servicio de campañas **no reentrena Gradient Boosting ni genera una segunda salida del modelo**. Consume las recomendaciones ya producidas por el flujo del recomendador.

### Flujo mensual

El flujo funcional es:

```text
clientes inactivos >= 270 días
        ↓
recomendaciones del mes vigente
        ↓
creación de campaña REACTIVA-YYYY-MM
        ↓
exclusiones y reglas de negocio
        ↓
1 a 3 recomendaciones por cliente
        ↓
cupón individual
        ↓
asignación balanceada de día 1 a 5
        ↓
campaign_active.csv
        ↓
revalidación de inactividad antes del envío
        ↓
Amazon SES
        ↓
actualización de estado
```

Cada campaña utiliza un identificador mensual determinístico:

```text
REACTIVA-YYYY-MM
```

La campaña nueva debe consumir recomendaciones correspondientes al período vigente. Si esa salida no existe o no es válida, el proceso no debe sustituirla silenciosamente por recomendaciones históricas.

### Elegibilidad y estados

El criterio operativo de reactivación continúa siendo:

```text
>= 270 días de inactividad
```

Antes de un envío se vuelve a verificar el estado del cliente.

Si el cliente ya realizó una compra, el registro pasa a:

```text
CANCELLED_REACTIVATED
```

y el correo no se envía.

Los estados operativos del envío son:

```text
PENDING
SENT
FAILED
CANCELLED_REACTIVATED
```

Los errores temporales pueden programar reintentos. Los errores definitivos, como un email inválido, se registran como fallo sin mantener reintentos innecesarios.

### Distribución de envíos

Los clientes son distribuidos de forma balanceada entre los días:

```text
1
2
3
4
5
```

del mes.

La asignación es determinística para una misma campaña.

El horario de negocio utilizado por el sender es:

```text
09:00 — Asia/Kolkata
```

La Lambda también permite informar explícitamente un `execution_time` durante pruebas controladas.

### Email mediante Amazon SES

El componente AWS:

```text
artifacts/AwsLambda/campaign_sender/
```

ejecuta el servicio diario de envío.

Sus responsabilidades son:

- cargar la campaña activa;
- cargar las transacciones operativas;
- verificar nuevamente la inactividad;
- construir el enlace individual de baja;
- enviar el correo mediante Amazon SES;
- administrar reintentos;
- actualizar estados;
- persistir el reporte técnico del envío.

El `campaign_sender` no:

- entrena Gradient Boosting;
- genera recomendaciones;
- crea la campaña mensual.

El mensaje posee versión HTML y texto plano e incluye, cuando corresponde:

- nombre del cliente;
- recomendaciones;
- porcentaje de descuento;
- código de cupón;
- vencimiento;
- enlace de baja.

El asunto configurado actualmente es:

```text
Increíbles Ofertas
```

### Configuración externa del sender

El sender requiere configuración de infraestructura mediante variables de entorno.

Los nombres utilizados por la implementación son:

```text
SES_SENDER_EMAIL
UNSUBSCRIBE_BASE_URL
UNSUBSCRIBE_SECRET
AWS_REGION
```

`SES_SENDER_EMAIL` debe corresponder a una identidad permitida por Amazon SES.

`UNSUBSCRIBE_BASE_URL` apunta al endpoint público utilizado para procesar la baja.

`UNSUBSCRIBE_SECRET` se utiliza solamente para generar y validar la firma HMAC.

Los **valores** de estas variables nunca deben incluirse en GitHub, documentación pública, capturas o archivos de configuración versionados.

### Baja de campañas

La Lambda:

```text
artifacts/AwsLambda/unsubscribe/
```

procesa el enlace individual incluido en el correo.

El enlace contiene:

```text
customer_id
campaign_id
token
```

El token se genera mediante HMAC a partir del cliente, la campaña y un secreto privado.

La Lambda de baja valida el token utilizando comparación segura y actualiza el estado correspondiente del cliente.

El mismo valor de:

```text
UNSUBSCRIBE_SECRET
```

debe estar configurado en el generador del enlace y en la Lambda que lo valida, pero el secreto existe exclusivamente en la configuración del entorno AWS.

### Robustez frente a CSV operativos

Los archivos de campaña pueden contener columnas completamente vacías antes del primer envío, por ejemplo:

```text
Last Attempt At
Sent At
Reactivated At
Last Error
```

Pandas puede inferir esas columnas vacías como `float64`.

El sender normaliza esas columnas a un tipo compatible antes de escribir timestamps ISO o mensajes de error, evitando fallos de tipo durante la actualización del estado de campaña.

La corrección no modifica la lógica de negocio, los estados ni los reintentos.

### Cupones

Cada cliente incluido en la campaña recibe un cupón individual.

Características vigentes:

```text
6 caracteres alfanuméricos en mayúsculas
10% de beneficio
un solo uso
vigencia hasta fin del mes de campaña
asociación a Customer ID
asociación a productos recomendados
registro del Transaction ID al consumirse
```

Estados principales:

```text
ACTIVE
REDEEMED
EXPIRED
```

ReActiva no funciona como sistema de facturación o POS. El servicio valida el cupón y registra su consumo, pero no sustituye el cálculo financiero final de una venta.

### Validación de cupones desde Streamlit

Cuando se informa un cupón durante una operación individual, Streamlit valida:

```text
cupón
+ Customer ID
+ mes de campaña
+ producto
+ estado ACTIVE
```

El consumo se persiste solamente después de confirmar el registro de la transacción o reconocer idempotentemente la misma transacción.

Al redimirse se registran:

```text
Coupon Status = REDEEMED
Coupon Redeemed At
Coupon Transaction ID
```

Un cupón ya redimido no puede reutilizarse con otro `Transaction ID`.

### Ciclo de reactivación

Cuando un cliente incluido en campaña vuelve a comprar:

- se registra la reactivación;
- se reinician los contadores asociados al ciclo sin compra;
- se elimina una pausa pendiente cuando corresponde;
- se conserva la trazabilidad de campaña y transacción.

La baja voluntaria y la pausa automática después de campañas sin compra son mecanismos diferentes.

### Persistencia en Amazon S3

La información de campañas utiliza el prefijo:

```text
campaigns/
```

con salidas como:

```text
campaigns/
├── campaign_active.csv
├── campaign_history.csv
├── customer_campaign_status.csv
└── reports/
```

`campaign_active.csv` representa el estado operativo del ciclo vigente.

Los procesos de campaña consumen y actualizan estos artefactos sin regenerar el modelo de recomendación.

### Validación operativa registrada — campaña septiembre 2026

Durante la validación funcional en AWS se generó correctamente la campaña:

```text
REACTIVA-2026-09
```

con:

```text
1.184 clientes objetivo
10% de descuento
1.184 cupones activos
```

La distribución programada quedó:

```text
Día 1: 237
Día 2: 237
Día 3: 237
Día 4: 237
Día 5: 236
```

En el momento de esa validación inicial la campaña se encontraba en estado operativo previo al envío:

```text
PENDING: 1.184
SENT: 0
REACTIVATED: 0
REDEEMED: 0
```

Estos valores constituyen una **fotografía operativa de esa ejecución** y no deben interpretarse como resultados comerciales futuros ni como una tasa esperada de conversión.

### Componentes AWS Lambda vigentes

Dentro de los artefactos versionados se encuentran actualmente:

```text
artifacts/AwsLambda/lambda_consolidator.py
artifacts/AwsLambda/monthly_campaign/
artifacts/AwsLambda/campaign_sender/
artifacts/AwsLambda/unsubscribe/
artifacts/AwsLambda/evidently_drift/
```

La generación de recomendaciones y la ejecución de campañas permanecen desacopladas.

La configuración de ECR, Lambda, Amazon SES, Function URL y EventBridge corresponde a infraestructura AWS y no debe contener secretos dentro del repositorio.

---

## Monitoreo de data drift con Evidently

ReActiva incorpora monitoreo de cambios de distribución mediante:

```text
Evidently 0.7.21
```

La lógica principal se encuentra en:

```text
src/reactiva/monitoring/drift.py
src/reactiva/monitoring/run_drift_monitoring.py
```

y el artefacto de Lambda en:

```text
artifacts/AwsLambda/evidently_drift/
```

El monitoreo está deliberadamente desacoplado de:

- entrenamiento;
- generación de recomendaciones;
- campañas;
- ejecución del sender.

Un resultado de drift **no bloquea automáticamente el modelo y no dispara reentrenamiento automático**.

### Ventanas temporales

El proceso construye dos ventanas consecutivas de:

```text
90 días
```

tomando como referencia la fecha máxima disponible en el dataset.

Conceptualmente:

```text
ventana de referencia — 90 días
             ↓
ventana actual — 90 días
             ↓
comparación Evidently
```

Antes de ejecutar el reporte se construyen las features de cliente utilizadas por el modelo.

### Features monitoreadas

La validación productiva actual monitorea cinco features:

```text
cat_count_Accessories
cat_count_Clothing
cat_count_Footwear
total_purchases
days_since_last_purchase
```

### Estado global

Evidently calcula drift a nivel de feature y también la proporción global:

```text
drift_share
```

El umbral global vigente es:

```text
0.50
```

Por lo tanto:

```text
drift_share >= 0.50 → DRIFT
drift_share < 0.50  → OK
```

Una feature puede presentar drift sin que el conjunto completo cambie su estado global.

### Salidas en S3

Las salidas más recientes se guardan en:

```text
monitoring/evidently/latest/drift_summary.csv
monitoring/evidently/latest/drift_features.csv
monitoring/evidently/latest/drift_report.json
```

El historial se conserva en:

```text
monitoring/evidently/history/drift_summary_history.csv
monitoring/evidently/history/drift_features_history.csv
monitoring/evidently/history/<run_id>/drift_report.json
```

Esto permite mantener tanto el último estado como la evolución de las ejecuciones.

### Validación operativa registrada — 02/09/2026

La primera ejecución real validada produjo:

```text
reference_rows: 1.027
current_rows: 714
features evaluadas: 5
features con drift: 1
drift_share: 0.20
umbral global: 0.50
estado global: OK
```

La feature detectada con drift fue:

```text
days_since_last_purchase
```

con un score aproximado:

```text
0.6473
```

El resultado:

```text
1 / 5 = 20%
```

se mantuvo por debajo del umbral global del 50%, por lo que el estado general permaneció `OK`.

Este resultado es una fotografía de esa ejecución y no debe presentarse como un valor permanente.

---

## Dashboard Power BI

El proyecto incorpora un dashboard interactivo de negocio, campañas y monitoreo desarrollado en Power BI.

El proyecto se almacena en formato:

```text
PBIP
```

dentro de:

```text
dashboard/
```

Las páginas vigentes son:

```text
1. Resumen Ejecutivo
2. Análisis Comercial
3. Reactivación y Campañas
4. Monitoreo del Modelo
```

### Resumen Ejecutivo

Presenta indicadores generales de negocio y calidad, entre ellos:

- transacciones;
- clientes;
- productos;
- ingresos;
- ticket promedio;
- devoluciones;
- evolución mensual;
- categorías;
- canal Online/Offline;
- indicadores de calidad.

### Análisis Comercial

Permite analizar:

- ubicación;
- categoría;
- marca;
- estado del cliente;
- productos;
- grupos de edad;
- métodos de pago.

La clasificación Activo/Inactivo utiliza el criterio operativo definido por el proyecto.

### Reactivación y Campañas

Consume el estado vigente de:

```text
campaign_active.csv
```

y permite seguir el recorrido desde la recomendación hasta la acción comercial.

Incluye:

- clientes objetivo;
- pendientes;
- enviados;
- clientes reactivados;
- tasa de reactivación;
- cupones activos;
- cupones redimidos;
- tasa de redención;
- descuento de campaña;
- distribución programada por día;
- recomendaciones 1, 2 y 3;
- estado de campaña.

Cuando todavía no existen envíos o redenciones, el dashboard muestra el estado real disponible y no inventa conversiones.

### Monitoreo del Modelo

La página:

```text
Monitoreo de Data Drift — Evidently
```

consume el historial generado por el proceso de monitoreo.

Incluye:

- estado global;
- drift observado;
- cantidad de features con drift;
- cantidad total de features;
- última evaluación;
- detalle por feature;
- score;
- método;
- umbral;
- evolución histórica.

El dashboard presenta las señales de monitoreo, pero no ejecuta reentrenamiento.

### Sincronización S3 → Power BI

Power BI no se conecta directamente a S3 dentro de esta implementación.

La actualización se realiza mediante:

```text
scripts/refresh_bi_data.py
```

que descarga y valida los archivos necesarios desde Amazon S3 hacia:

```text
dashboard/data/
```

Actualmente sincroniza:

```text
monitoring/evidently/history/drift_summary_history.csv
monitoring/evidently/history/drift_features_history.csv
campaigns/campaign_active.csv
```

El archivo:

```text
actualizar_dashboard.bat
```

automatiza el flujo local:

```text
ejecutar .bat
      ↓
usar Python del entorno virtual
      ↓
descargar datos desde S3
      ↓
validar archivos
      ↓
actualizar dashboard/data/
      ↓
abrir Power BI
      ↓
presionar Actualizar
```

Este mecanismo permite mantener el dashboard portable sin afirmar una conexión directa Power BI → S3 ni depender obligatoriamente de Power BI Service.

### Portabilidad del proyecto Power BI

Las consultas locales utilizan el parámetro:

```text
RutaDatosBI
```

como ruta base hacia `dashboard/data`.

De esta manera otra computadora puede utilizar el proyecto ajustando un único parámetro de ruta local en lugar de modificar cada consulta individualmente.

### Estado de pruebas y validación

Después de integrar el monitoreo con Evidently, la suite completa del proyecto registró:

```text
144 passed
```

Posteriormente se realizó un ajuste puntual de compatibilidad de tipos en `src/reactiva/campaigns/sender.py` para columnas vacías provenientes de CSV.

Ese ajuste final fue validado mediante:

```bash
python -m py_compile src/reactiva/campaigns/sender.py
```

sin modificar la lógica funcional del sender.

Los detalles de problemas encontrados, causas y soluciones se mantienen en:

```text
docs/troubleshooting/README.md
```

---

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

- Evidently;

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

## Consolidador de transacciones — AWS Lambda

El proyecto incluye un componente AWS Lambda de consolidación cuyo código versionado se encuentra en:

```text
artifacts/AwsLambda/lambda_consolidator.py
```

El consolidador integra transacciones operativas almacenadas en S3, valida su estructura, resuelve identidades temporales, mantiene un registro persistente de clientes y genera auditorías.

### Responsabilidades principales

El flujo actual contempla:

```text
staging
   ↓
lectura de CSV
   ↓
validación de columnas
   ↓
conversión de Purchase Date
   ↓
resolución de PENDING-UUID
   ↓
reconciliación operativa de duplicados
   ↓
escritura del dataset consolidado
   ↓
actualización del customer registry
   ↓
auditorías
```

La implementación conserva como esquema esperado las 28 columnas canónicas.

### Resolución de clientes temporales

Para registros con:

```text
PENDING-<uuid>
```

la implementación actual utiliza como señales de matching:

```text
Customer Phone normalizado
Customer Full Name normalizado
Age con tolerancia
```

La tolerancia de edad configurada en el consolidador es de:

```text
2 años
```

`Customer Email` se conserva dentro del registro de cliente, pero la implementación vigente no lo utiliza como señal de matching.

Si no existe una coincidencia válida se crea un nuevo:

```text
Customer ID = CUSTXXXXXX
```

y la decisión queda registrada en la auditoría de identidad.

### Reconciliación adicional de duplicados

La validación general del proyecto considera `Transaction ID` como identidad única de una operación.

Además, el consolidador vigente mantiene una defensa operativa adicional para detectar filas prácticamente equivalentes: agrupa por campos de identidad de la compra y compara `Purchase Date`.

La tolerancia implementada es:

```text
<= 2 segundos
```

Cuando se aplica esta regla se conserva trazabilidad sobre:

- transacción retenida;
- transacción clasificada como duplicada;
- motivo;
- diferencia temporal;
- timestamp de procesamiento.

Esta regla adicional pertenece al consolidador y no reemplaza las validaciones de integridad de `Transaction ID` realizadas en otras capas.

### Persistencia y auditoría

Entre las salidas operativas utilizadas por este componente se encuentran:

```text
customer_shopping_behavior-clean.csv
customer_registry/
duplicate_audit/
identity_merge_audit/
```

Los objetos de staging solamente deben eliminarse después de completar correctamente las escrituras correspondientes.

### Despliegue

Los artefactos de AWS Lambda se mantienen bajo:

```text
artifacts/AwsLambda/
```

La construcción y publicación de imágenes, la configuración de funciones y los permisos de infraestructura se realizan con credenciales externas al repositorio.

El README no incluye comandos con cuentas, URIs privadas ni secretos de AWS.

# Resolución de identidad de clientes y consolidación de transacciones

## Descripción general

El consolidador incorpora un proceso de resolución de identidad destinado a que las transacciones pertenecientes a una misma persona mantengan un `Customer ID` persistente.

El objetivo principal es evitar la fragmentación del historial cuando un mismo cliente aparece en distintos archivos de staging con un identificador temporal `PENDING-*` o con variaciones en algunos datos de perfil.

El flujo general es:

```text
Transacciones en staging
        ↓
Validar estructura
        ↓
Convertir Purchase Date
        ↓
Resolver identidad del cliente
        ↓
Detectar transacciones duplicadas
        ↓
Eliminar duplicados
        ↓
Escribir transacciones consolidadas
        ↓
Actualizar registro de clientes
        ↓
Escribir auditorías de identidad y duplicados
```

## Resolución de identidad del cliente

Se utiliza un registro persistente de clientes como referencia para identidades previamente conocidas.

El registro conserva información relevante para resolver un cliente, incluyendo los campos disponibles y normalizados definidos por el consolidador.

Cuando una transacción llega con un `Customer ID` temporal `PENDING-*`, el sistema intenta asociarla a un cliente existente antes de crear un nuevo identificador persistente.

### Estrategia de coincidencia de identidad

La implementación actual del consolidador utiliza una regla conservadora basada en la combinación de:

```text
teléfono normalizado
+ nombre completo normalizado
+ edad dentro de la tolerancia configurada
```

`Customer Email` se conserva como atributo informativo, pero no se utiliza actualmente como señal de matching en `lambda_consolidator.py`.

Si ninguna regla permite resolver el cliente, se crea un nuevo `Customer ID` persistente.

El teléfono se normaliza antes de compararse para que las diferencias de formato no impidan reconocer un mismo número.

Por ejemplo:

```text
+91 79794369905
917974369905
91-7979-436-9905
```

pueden normalizarse a una representación numérica comparable.

## Uso conjunto de teléfono, nombre completo y edad

El email se conserva como dato de perfil, pero la implementación vigente no lo utiliza para resolver identidades porque una persona puede utilizar una dirección distinta en una compra posterior.

Si el email fuera el único criterio, el mismo cliente podría quedar representado de esta forma:

```text
Compra 1
Customer ID → CUST001000
Email → customer@email.com
        ↓
Compra 2
Email → another@email.com
        ↓
Nuevo Customer ID → CUST001001
```

Eso produciría fragmentación del historial del cliente.

La combinación de:

```text
Teléfono + nombre completo + edad
```

agrega una capa de validación que permite reconocer al cliente cuando cambia el email.

La intención no es considerar un atributo individual como prueba suficiente de identidad, sino combinar señales para obtener una decisión más robusta.

## Motivo para no utilizar solamente el teléfono

El teléfono tampoco es una identidad infalible: puede ser compartido, reutilizado o registrado de forma incorrecta.

De forma similar:

- teléfono + nombre todavía puede presentar casos ambiguos;
- nombre por sí solo es insuficiente;
- edad por sí sola es insuficiente;
- email puede cambiar entre transacciones.

La combinación seleccionada busca una regla automática más conservadora sin perder la continuidad del historial de clientes recurrentes.

También puede aplicarse una tolerancia sobre la edad cuando la información histórica cambia o se registra con pequeñas diferencias.

## Consideración de costo-beneficio del negocio

Existen dos tipos principales de error al resolver identidad.

### Fusión incorrecta

El sistema podría asociar teóricamente dos personas diferentes si coinciden las señales utilizadas para resolver identidad.

Ese riesgo debe mitigarse mediante reglas conservadoras y auditoría. Si ocurre una fusión incorrecta, el registro de auditoría permite investigar la decisión y corregirla.

### Separación incorrecta

El caso opuesto consiste en crear un nuevo `Customer ID` para una persona que ya existía.

Por ejemplo:

```text
Compra 1 → CUST001000
Compra 2 → CUST001001
```

aunque ambas operaciones pertenezcan al mismo cliente.

Esto genera costos persistentes para el negocio:

- historial de compras fragmentado;
- perfil de cliente incorrecto;
- menor calidad de personalización;
- recomendaciones menos confiables;
- métricas de comportamiento distorsionadas;
- información de fidelización fragmentada;
- más registros duplicados de clientes;
- mayor trabajo de reconciliación posterior.

La estrategia implementada busca reducir esta fragmentación manteniendo trazabilidad sobre cada decisión automática.

## Auditoría

Las decisiones de resolución de identidad se registran en auditorías.

Para cada cliente temporal resuelto pueden conservarse datos como:

- identificador temporal original;
- `Customer ID` resuelto;
- tipo de resolución;
- señales de coincidencia utilizadas;
- marca temporal de la resolución.

Por ejemplo:

```text
PENDING-XXXX
        ↓
CUST001000
        ↓
resolution = merged_existing
        ↓
match_signals = phone+name+age
```

De esta manera la resolución automática es trazable y no una modificación silenciosa de identidades.

## Detección de duplicados

La detección de duplicados forma parte del proceso de consolidación y se ejecuta después de resolver identidad.

Las operaciones se comparan según las reglas configuradas por el consolidador. Cuando una transacción se clasifica como duplicada, se conserva la operación de referencia y la duplicada se registra en la auditoría correspondiente.

La auditoría puede incluir:

- transacción eliminada;
- transacción retenida;
- diferencia entre fechas;
- motivo de duplicación;
- marca temporal del procesamiento.

## Orden de procesamiento

La resolución de identidad se realiza intencionalmente **antes de la detección de duplicados**.

Esto es importante porque dos operaciones de la misma persona podrían llegar con identificadores temporales diferentes:

```text
Transacción A
Customer ID = PENDING-AAA

Transacción B
Customer ID = PENDING-BBB
```

Después de resolver identidad:

```text
Transacción A
Customer ID = CUST001000

Transacción B
Customer ID = CUST001000
```

La detección de duplicados puede entonces trabajar sobre la identidad ya resuelta.

Conceptualmente:

```text
Resolver QUIÉN es el cliente
        ↓
Determinar QUÉ transacciones son duplicadas
```

## Registro de clientes y auditorías

El registro persistente y las auditorías cumplen responsabilidades diferentes.

### Registro de clientes

Responde:

> **¿Quién es este cliente?**

Se utiliza como referencia persistente para futuras ejecuciones del consolidador.

### Auditoría de identidad

Responde:

> **¿Qué decisión tomó el sistema al resolver este cliente y qué señales utilizó?**

### Auditoría de duplicados

Responde:

> **¿Qué transacción se consideró duplicada, cuál se conservó y por qué?**

Esta separación mantiene los datos persistentes de identidad diferenciados de los registros históricos del procesamiento.

## Resultado

El proceso de consolidación proporciona una capa persistente de identidad de clientes y conserva la trazabilidad de las transacciones procesadas.

```text
                  REGISTRO DE CLIENTES
                           │
                           ▼
                    Identidad del cliente
                           │
                           ▼
STAGING → RESOLUCIÓN DE IDENTIDAD → DETECCIÓN DE DUPLICADOS
                                      │
                                      ▼
                            TRANSACCIONES LIMPIAS
                                      │
                                      ▼
                              DATASET CONSOLIDADO
```

Este enfoque reduce la fragmentación de identidad, preserva el historial de compras, mejora la información disponible para personalización y recomendación, y mantiene auditoría tanto para las decisiones de identidad como para la eliminación de duplicados.
