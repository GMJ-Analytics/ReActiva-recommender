# Solución de problemas

En esta carpeta se documentarán los problemas encontrados durante el desarrollo del proyecto.

Cada registro deberá incluir:

- Fecha
- Contexto
- Problema
- Causa
- Solución aplicada
- Resultado
- Prevención

## 2026-08-12 - PR con cambios de una tarea anterior

### Contexto

Durante la revisión del PR #3 se detectó que la branch utilizada contenía código previo de Streamlit que el equipo había decidido no integrar al proyecto en esa instancia.

### Problema

El Pull Request incluía cambios que no correspondían al trabajo actual y que podían incorporarse accidentalmente a `main`.

### Causa

Se reutilizó una branch existente para trabajos distintos en lugar de crear una nueva branch desde `main` actualizado para cada tarea.

### Solución aplicada

Se revisó el diff del PR antes de aprobarlo, se decidió cerrarlo sin realizar el merge y se eliminó la branch asociada.

### Resultado

El código no deseado no fue incorporado a `main` y el repositorio mantuvo la versión acordada por el equipo.

### Prevención

A partir de este caso se refuerza el flujo de trabajo:

`Issue -> branch propia desde main actualizado -> desarrollo -> Pull Request -> revisión -> merge -> eliminación de la branch`

Cada nueva tarea debe trabajarse en una branch independiente para evitar arrastrar cambios de trabajos anteriores.

---

## 2026-08-18 - Archivo de origen en S3 incompatible con su extensión

### Contexto

Durante la preparación de datos de la Issue #28 se intentó cargar el dataset principal desde AWS S3 mediante la función `cargar_datos()`.

### Problema

La lectura del archivo fallaba con un error de decodificación al intentar procesarlo como CSV.

### Causa

El objeto almacenado en S3 no correspondía correctamente al formato indicado por su extensión `.csv`. El contenido presentaba una estructura incompatible con un CSV válido para el flujo de carga del proyecto.

### Solución aplicada

Se corrigió el archivo almacenado en S3 y se volvió a ejecutar la carga mediante `cargar_datos()`.

### Resultado

El dataset pudo cargarse correctamente con:

- 10.000 filas.
- 27 columnas.
- 3.291 clientes únicos.
- `Customer Full Name` presente.
- `Customer Email` presente.
- `Frequency of Purchases` ausente.

La carga quedó nuevamente operativa para auditoría, validación, EDA y preparación de datos.

### Prevención

Después de reemplazar o actualizar un dataset en S3 se debe realizar una validación mínima de carga antes de continuar con el pipeline:

- confirmar que la extensión coincida con el formato real del archivo;
- verificar que el archivo pueda abrirse mediante la función de carga oficial del proyecto;
- comprobar dimensiones y columnas esperadas;
- evitar continuar con auditoría o modelado hasta validar correctamente la fuente.

---

## 2026-08-18 - Eliminación incorrecta de transacciones legítimas por deduplicación

### Contexto

Durante la validación de la limpieza reproducible de datos de la Issue #28 se revisó la regla utilizada para detectar transacciones duplicadas.

### Problema

La lógica inicial utilizaba como clave:

`Customer ID + Item Purchased + Purchase Date`

Con esa combinación podían identificarse como duplicadas compras legítimas realizadas por un mismo cliente sobre el mismo producto y fecha.

Posteriormente se incorporó `Transaction ID` dentro de una clave compuesta, pero durante la revisión final se determinó que la identidad transaccional debía depender directamente de `Transaction ID`.

### Causa

`Transaction ID` es el identificador único de una operación.

Dos registros que tengan diferentes `Transaction ID` representan transacciones distintas aunque coincidan en cliente, producto y fecha.

Por el contrario, dos registros distintos que compartan el mismo `Transaction ID` representan un conflicto de integridad y no deben resolverse silenciosamente eliminando una de las filas.

### Solución aplicada

La validación quedó basada en:

`Transaction ID`

como identidad única de la operación.

La clave `duplicate_key_rows` se mantiene en el reporte por compatibilidad con los consumidores existentes, pero actualmente representa la cantidad de `Transaction ID` duplicados.

La limpieza conserva la eliminación de filas completamente idénticas, pero no elimina silenciosamente conflictos donde un mismo `Transaction ID` identifica registros diferentes.

### Resultado

Dos compras del mismo cliente, producto y fecha con distintos `Transaction ID` permanecen como transacciones independientes.

Un `Transaction ID` repetido se considera un problema de integridad que debe ser corregido antes de continuar.

### Prevención

Toda modificación futura de la lógica de deduplicación debe validar al menos:

- `Transaction ID` vacío;
- `Transaction ID` duplicado;
- compras con mismo cliente, producto y fecha pero distintos `Transaction ID`;
- registros diferentes asociados al mismo `Transaction ID`.

---

## 2026-08-17 - requirements.txt con codificación incorrecta y dependencias AWS incompatibles

### Contexto

Durante la actualización del entorno del proyecto se revisó el archivo `requirements.txt` utilizado para instalar las dependencias compartidas por los integrantes del equipo.

### Problema

El archivo presentaba dos inconvenientes que afectaban su utilización confiable:

- estaba almacenado con codificación UTF-16 en lugar de UTF-8;
- las versiones de algunas dependencias relacionadas con AWS requerían ser compatibilizadas.

La codificación provocaba que distintas herramientas interpretaran incorrectamente el archivo y dificultaba su revisión normal desde Git.

La combinación de dependencias AWS también debía quedar validada para evitar conflictos durante la instalación del entorno.

### Causa

El archivo había sido generado o guardado previamente utilizando una codificación diferente a la utilizada normalmente por los archivos de texto del repositorio.

Además, paquetes relacionados con AWS poseen dependencias entre sí y sus versiones no pueden seleccionarse de forma completamente independiente.

Entre los paquetes involucrados se encontraban:

- `aiobotocore`;
- `boto3`;
- `botocore`;
- `s3fs`;
- `fsspec`.

### Solución aplicada

Se normalizó `requirements.txt` a codificación UTF-8.

También se ajustaron y validaron las versiones relacionadas con AWS.

La combinación validada incluyó:

```text
aiobotocore==3.9.0
boto3==1.43.56
botocore==1.43.56
s3fs==2026.7.0
fsspec==2026.7.0
```

Posteriormente se ejecutaron nuevamente los controles de instalación y consistencia del entorno.

### Resultado

El archivo `requirements.txt` quedó correctamente interpretable como archivo de texto UTF-8 y pudo utilizarse como fuente reproducible de dependencias.

La validación mediante:

```bash
python -m pip check
```

finalizó sin dependencias rotas.

La configuración AWS quedó operativa con las versiones establecidas.

### Prevención

El archivo `requirements.txt` debe mantenerse en UTF-8.

Después de modificar dependencias se recomienda ejecutar:

```bash
python -m pip install -r requirements.txt
```

y posteriormente:

```bash
python -m pip check
```

Cuando se actualicen paquetes relacionados con AWS, deben revisarse conjuntamente las restricciones de compatibilidad entre `aiobotocore`, `boto3`, `botocore`, `s3fs` y `fsspec`.

También debe evitarse reemplazar versiones ya validadas sin comprobar nuevamente la instalación completa del entorno.

---

## 2026-08-24 - Duplicación de dependencias y lógica del recomendador

### Contexto

Durante la integración de los cambios de modelado, Streamlit, Docker y contexto correspondientes a la Issue #47 se revisó cómo los diferentes componentes consumían las dependencias y la lógica de recomendación.

### Problema

Existían implementaciones duplicadas en diferentes ubicaciones del repositorio:

```text
requirements.txt
app/requirements.txt
```

y:

```text
app/recommender.py
src/reactiva/recommender/recommender.py
```

Mantener dos archivos de dependencias y dos implementaciones del recomendador generaba el riesgo de que Streamlit, Docker y los módulos de `src/reactiva` terminaran ejecutando versiones diferentes de la misma lógica.

Una modificación realizada sobre una copia podía no propagarse a la otra.

### Causa

Durante las primeras etapas del proyecto se fueron incorporando componentes de forma independiente.

Streamlit disponía de archivos propios dentro de `app/`, mientras que la arquitectura general del proyecto ya había definido `src/reactiva/` como ubicación para la lógica reutilizable.

Al avanzar la integración, ambas estructuras comenzaron a superponerse.

### Solución aplicada

Se definió:

```text
requirements.txt
```

ubicado en la raíz del repositorio como archivo canónico de dependencias.

Se eliminó:

```text
app/requirements.txt
```

También se definió:

```text
src/reactiva/recommender/recommender.py
```

como implementación canónica del recomendador.

Se eliminó:

```text
app/recommender.py
```

Streamlit y Docker fueron actualizados para consumir directamente la implementación ubicada dentro de `src/reactiva`.

### Resultado

El proyecto quedó con una única fuente de dependencias y una única implementación reutilizable del recomendador.

Actualmente:

```text
requirements.txt
```

es utilizado por el entorno local y Docker.

Y:

```text
src/reactiva/recommender/recommender.py
```

es utilizado como fuente principal de la lógica de recomendación.

Esto reduce el riesgo de divergencias entre ejecución local, Streamlit, Docker y futuros componentes del proyecto.

La suite completa fue ejecutada después de la integración y registró:

```text
19 passed
```

Además:

```bash
python -m pip check
```

finalizó sin dependencias rotas.

### Prevención

Antes de crear una nueva implementación de una función existente debe verificarse si esa responsabilidad ya se encuentra implementada dentro de `src/reactiva`.

La lógica reutilizable debe permanecer dentro del paquete canónico y los consumidores, como Streamlit, notebooks o futuras APIs, deben importarla en lugar de mantener copias independientes.

De la misma manera, las dependencias comunes del proyecto deben mantenerse en un único archivo canónico mientras no exista una necesidad técnica explícita y documentada de separar entornos.

---

## 2026-08-24 - Runtime de Docker incompatible con el tipo de aplicación

### Contexto

Durante la validación de Docker realizada como parte de la integración de la Issue #47 se revisó el comando utilizado para iniciar la aplicación dentro del contenedor.

El proyecto contiene dependencias relacionadas con una futura API, incluyendo `Uvicorn`, pero la aplicación actualmente implementada en:

```text
app/app.py
```

es una aplicación Streamlit.

### Problema

La existencia de dependencias asociadas a FastAPI/Uvicorn podía llevar a configurar el contenedor como si `app.py` correspondiera a una aplicación ASGI.

Sin embargo, el runtime actual del proyecto es Streamlit.

Utilizar un servidor ASGI para iniciar este archivo no representa correctamente el tipo de aplicación existente y evita disponer de una configuración Docker coherente con la ejecución real del proyecto.

### Causa

La arquitectura prevista contempla una futura capa de API, mientras que la interfaz desarrollada actualmente utiliza Streamlit.

Durante la evolución del proyecto coexistieron dependencias correspondientes a ambas etapas, aunque la API todavía no constituye el punto de entrada actual de la aplicación.

### Solución aplicada

Se configuró el `Dockerfile` para iniciar explícitamente Streamlit mediante:

```text
streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

También se definió:

```dockerfile
EXPOSE 8501
```

`Uvicorn` se mantuvo como dependencia disponible para la futura implementación de una API, pero dejó de considerarse el runtime correspondiente a `app.py`.

### Resultado

La imagen Docker pudo construirse correctamente desde la raíz del repositorio.

Se validó la ejecución del contenedor utilizando variables de entorno y credenciales AWS suministradas externamente.

Streamlit quedó accesible desde:

```text
http://localhost:8501
```

El contenedor utiliza además el `requirements.txt` canónico y la implementación del paquete `reactiva` ubicada dentro de `src/reactiva`.

### Prevención

El comando de inicio de un contenedor debe corresponder al framework que realmente implementa el entrypoint utilizado.

Para el estado actual del proyecto:

```text
app.py -> Streamlit -> puerto 8501
```

Una futura implementación de FastAPI deberá disponer de su propio módulo o entrypoint claramente identificado.

La incorporación futura de una API no debe reemplazar accidentalmente el runtime de Streamlit mientras ambos componentes continúen cumpliendo responsabilidades diferentes.

---

## 2026-08-26 - Rutas locales absolutas en Power BI

### Contexto

Durante el desarrollo del dashboard de la Issue #61 se detectó que las consultas del proyecto Power BI almacenaban directamente la ruta absoluta de la computadora utilizada para crearlo.

### Problema

Las seis consultas principales contenían rutas similares a:

`C:\Users\<usuario>\...\ReActiva-recommender\dashboard\data\archivo.csv`

Esto impedía que otro integrante pudiera abrir y actualizar el dashboard desde una ubicación diferente sin modificar individualmente cada consulta.

### Causa

Power BI generó automáticamente referencias absolutas al utilizar archivos CSV locales como origen de datos.

### Solución aplicada

Se creó en Power Query el parámetro:

`RutaDatosBI`

Las seis consultas utilizan ahora ese único parámetro como ruta base:

- `FactTransacciones`
- `DimFecha`
- `DimCliente`
- `DimProducto`
- `CalidadResumen`
- `CalidadColumnas`

Cada archivo se resuelve a partir del parámetro, por ejemplo:

`RutaDatosBI & "\bi_transactions.csv"`

### Resultado

La ruta local quedó centralizada en un único punto. Al utilizar el proyecto desde otra computadora solamente es necesario modificar `RutaDatosBI` para que apunte a la carpeta local `dashboard/data`.

### Prevención

Toda nueva fuente local utilizada por Power BI debe depender de un parámetro de ruta y no incorporar directamente rutas absolutas dentro de cada consulta.

---

## 2026-08-26 - Interpretación incorrecta de decimales por configuración regional en Power BI

### Contexto

Durante la construcción del modelo de Power BI de la Issue #61 se importaron tablas CSV generadas por Python.

### Problema

La detección automática de tipos de Power Query interpretó algunos valores con punto decimal utilizando una configuración regional incompatible.

Por ejemplo, valores como:

`6065.5`

podían ser interpretados como:

`60655`

alterando métricas y porcentajes del dashboard.

### Causa

Los CSV utilizan el punto (`.`) como separador decimal, mientras que la configuración regional utilizada por Power BI esperaba otra representación numérica.

### Solución aplicada

En las consultas afectadas se evitó la detección automática de tipos y los campos numéricos necesarios se convirtieron explícitamente utilizando una configuración regional compatible con el formato del CSV.

### Resultado

Los valores decimales y porcentajes quedaron correctamente interpretados en el modelo y las métricas del dashboard recuperaron sus valores esperados.

### Prevención

Al importar CSV generados por Python en Power BI:

- evitar depender únicamente de la detección automática de tipos;
- validar manualmente métricas decimales después de la importación;
- utilizar conversión de tipo con configuración regional explícita cuando el archivo utilice punto decimal.

---

## 2026-08-28 - Incompatibilidad entre el nuevo modelo de reactivación y Streamlit

### Contexto

Después de integrar a `main` la nueva implementación del recomendador basada en Gradient Boosting para clientes inactivos, se actualizó la rama de Streamlit con los cambios más recientes del repositorio.

La aplicación Streamlit también genera recomendaciones comerciales durante las ventas realizadas en el punto de venta.

### Problema

Streamlit continuaba importando y utilizando:

```python
build_customer_similarity()
```

para generar recomendaciones mediante similitud Customer-Customer.

Esta lógica había quedado obsoleta respecto de la arquitectura vigente del recomendador.

### Causa

La similitud cliente-cliente correspondía a una etapa anterior del desarrollo y todavía permanecía conectada al flujo de Streamlit.

El modelo de reactivación ya había evolucionado hacia Gradient Boosting y el flujo operativo de venta local podía resolverse utilizando la similitud entre productos a partir del producto que el cliente está comprando.

### Solución aplicada

Se mantuvo sin modificaciones la implementación de Gradient Boosting utilizada para clientes inactivos.

La similitud Customer-Customer fue eliminada del flujo de Streamlit.

No se restauró:

```python
build_customer_similarity()
```

ni la similitud coseno entre clientes.

La arquitectura vigente quedó:

```text
Cliente inactivo >= 270 días
→ Gradient Boosting
→ recomendación de reactivación
```

```text
Cliente existente Offline
→ producto comprado actualmente
→ Item-to-Item
→ recomendación
```

```text
Cliente nuevo Offline
→ producto comprado actualmente
→ Item-to-Item
→ recomendación
```

Las operaciones Online se registran, pero no generan recomendaciones en Streamlit.

### Resultado

Streamlit utiliza Item-to-Item para las recomendaciones asociadas a ventas locales tanto de clientes existentes como nuevos.

El modelo Gradient Boosting mantiene exclusivamente su responsabilidad sobre clientes inactivos.

La lógica User-Based / Customer-Customer deja de formar parte del flujo productivo vigente.

### Prevención

Las funciones utilizadas durante etapas experimentales no deben mantenerse en el flujo productivo únicamente por compatibilidad histórica.

Antes de conservar o restaurar una función debe verificarse si continúa formando parte de la arquitectura vigente y si existe un consumidor real que todavía la necesite.

---

## 2026-08-28 - Cache indefinido del dataset histórico en Streamlit

### Contexto

Streamlit utiliza el dataset histórico canónico configurado mediante:

```text
DATASET_URI
```

para mostrar información de clientes y construir recomendaciones.

La carga del dataset estaba implementada mediante:

```python
@st.cache_data(show_spinner='Leyendo dataset historico...')
```

### Problema

El cache no tenía definido un tiempo de expiración.

Esto permitía que una instancia de Streamlit mantuviera en memoria una versión antigua del dataset aun después de que el dataset canónico hubiera sido actualizado en S3.

### Causa

`st.cache_data` conserva el resultado de la función mientras Streamlit considere válida la entrada cacheada.

Al no existir un `ttl`, la aplicación no tenía una política explícita para volver a consultar periódicamente la fuente configurada.

### Solución aplicada

Se incorporó un tiempo de vida de una hora:

```python
@st.cache_data(
    ttl=3600,
    show_spinner='Leyendo dataset historico...'
)
```

De esta manera Streamlit puede reutilizar el dataset en memoria durante la operación normal y volver a consultar la fuente canónica una vez vencido el cache.

### Resultado

La aplicación evita realizar una lectura del dataset histórico en cada interacción y, al mismo tiempo, deja de mantener indefinidamente una copia potencialmente desactualizada.

La versión actual adopta deliberadamente una política de consistencia diaria:

```text
ventas del día
→ staging
→ consolidación nocturna
→ dataset canónico actualizado
→ recomendaciones posteriores
```

Las transacciones todavía presentes en staging no necesitan afectar las recomendaciones generadas durante el mismo día.

La actualización en tiempo real o casi real puede incorporarse posteriormente como una mejora de escalabilidad si el caso de negocio lo requiere.

### Prevención

Toda fuente remota utilizada mediante cache debe definir explícitamente:

- cuándo puede considerarse válida la información cacheada;
- cuándo debe releerse la fuente;
- qué nivel de consistencia necesita el caso de negocio.

No debe eliminarse el cache únicamente para obtener información más reciente si el sistema no requiere consistencia en tiempo real, ya que eso puede aumentar innecesariamente las lecturas contra servicios externos.

---

## 2026-08-28 - Separación de staging para ventas individuales y cargas masivas

### Contexto

Streamlit permite registrar transacciones de dos formas diferentes:

- ventas individuales realizadas desde el flujo de atención;
- cargas masivas utilizadas para representar ventas provenientes del canal online.

Ambos flujos deben persistir información en Amazon S3 antes de que las transacciones sean incorporadas al dataset histórico canónico.

### Problema

La aplicación disponía de dos caminos de escritura hacia S3, pero no existía una separación suficientemente explícita entre los archivos generados por ventas individuales y los archivos correspondientes a cargas masivas.

Utilizar una ubicación genérica dificultaría posteriormente:

- identificar el origen de cada archivo;
- aplicar reglas específicas durante la consolidación;
- auditar cada tipo de ingreso;
- evitar confundir una carga batch con una venta registrada individualmente.

### Causa

Los dos mecanismos de ingreso fueron desarrollados inicialmente como funcionalidades independientes.

La arquitectura de consolidación todavía no se encontraba definida completamente y el helper de subida mantenía un prefijo genérico como valor por defecto.

### Solución aplicada

Se definieron dos rutas independientes dentro de staging:

```text
staging/individual/
```

para las transacciones registradas individualmente desde Streamlit, y:

```text
staging/batch/
```

para las cargas masivas.

El flujo queda:

```text
venta individual
→ validación
→ objeto independiente
→ staging/individual/
```

y:

```text
archivo masivo
→ validación
→ limpieza
→ staging/batch/
```

La persistencia utiliza identificadores estables de la operación para evitar que una segunda ejecución accidental genere una segunda copia lógica de la misma transacción o lote.

### Resultado

Las ventas individuales se almacenan bajo:

```text
staging/individual/
```

y las cargas masivas bajo:

```text
staging/batch/
```

La separación deja preparado el origen de datos para que el proceso nocturno pueda consumir ambos tipos de staging de forma controlada.

### Prevención

Las distintas fuentes operativas no deben escribir indiscriminadamente sobre una misma ubicación genérica cuando posteriormente requieren trazabilidad o tratamiento diferente.

Toda nueva fuente de ingesta debe definir explícitamente:

- origen;
- prefijo de staging;
- formato esperado;
- estrategia de identificación única;
- reglas de validación;
- mecanismo de consolidación.

El dataset canónico no debe modificarse directamente desde interfaces concurrentes como Streamlit mientras exista una capa de staging destinada a controlar esa integración.

---

## 2026-08-28 - Validación preventiva de carga masiva y robustez del visor de logs

### Contexto

Durante la revisión funcional de Streamlit se analizaron dos puntos defensivos:

- la carga de archivos CSV masivos;
- la visualización administrativa de logs estructurados.

Ambos componentes podían funcionar correctamente en condiciones normales, pero necesitaban controles adicionales para evitar fallas frente a entradas inesperadas.

### Problema

En la carga masiva, el archivo podía llegar a ser procesado por Pandas sin una validación previa de tamaño.

Esto implicaba que un archivo excesivamente grande pudiera consumir memoria innecesariamente antes de ejecutar las validaciones de contenido.

En el visor de auditoría, el filtro por nivel asumía que todos los registros contenían una columna:

```text
level
```

con valores válidos.

Además, leer indefinidamente un archivo de log completo podía generar un consumo innecesario de memoria a medida que aumentara su tamaño.

### Causa

Las validaciones existentes estaban orientadas principalmente a la calidad interna del dataset una vez cargado.

El tamaño del archivo todavía no se verificaba antes de su lectura.

Por otra parte, los logs generados actualmente incluyen normalmente el campo `level`, pero el visor administrativo no contemplaba defensivamente registros históricos o externos con esquemas incompletos ni el crecimiento continuo del archivo.

### Solución aplicada

Para la carga masiva se definió un límite operativo de:

```text
20 MB
```

El límite se aplica en dos niveles.

A nivel del framework Streamlit se configuró:

```text
.streamlit/config.toml
```

con:

```toml
[server]
maxUploadSize = 20
```

La configuración también se copia dentro de la imagen Docker mediante:

```dockerfile
COPY .streamlit ./.streamlit
```

Además, la aplicación mantiene una validación defensiva propia antes de procesar el CSV.

Antes de procesar el archivo se verifica:

```text
archivo vacío
→ rechazar
```

y:

```text
archivo > 20 MB
→ rechazar
```

Para el visor de logs se mantiene una normalización defensiva del campo `level`.

Si la columna no existe o contiene valores nulos se utiliza:

```text
UNKNOWN
```

La lectura del visor también se mantiene acotada para evitar cargar indefinidamente un log completo en memoria.

### Resultado

La carga masiva quedó protegida frente a archivos vacíos o superiores al límite operativo definido por la aplicación.

El visor de auditoría quedó preparado para tolerar registros con esquemas incompletos y para limitar el volumen de información cargado simultáneamente.

### Prevención

Las validaciones de archivos deben diferenciar dos niveles:

```text
validación del contenedor
→ tamaño, existencia y posibilidad de lectura

validación del contenido
→ esquema, tipos, nulos, duplicados, rangos y reglas de negocio
```

De la misma manera, las herramientas de auditoría deben tolerar registros históricos o externos parcialmente incompletos y evitar lecturas ilimitadas de archivos que pueden crecer de forma continua.

---

## 2026-08-29 - Lectura incorrecta de CSV desde Amazon S3

### Contexto

Durante la revisión del flujo de carga se analizó:

```text
src/reactiva/data/load_data.py
```

### Problema

El objeto devuelto por S3 en:

```python
response['Body']
```

se estaba utilizando directamente para construir un DataFrame.

Esto no interpreta correctamente el contenido del archivo CSV.

### Causa

`response['Body']` representa un stream de bytes y no una estructura tabular lista para convertirse directamente mediante `pd.DataFrame()`.

### Solución aplicada

El flujo se corrigió para:

```text
leer Body
→ decodificar UTF-8
→ StringIO
→ pd.read_csv()
```

### Resultado

El contenido descargado desde S3 se interpreta correctamente como CSV antes de construir el DataFrame utilizado por el proyecto.

### Prevención

Los objetos obtenidos desde servicios de almacenamiento deben procesarse según el formato real del archivo.

Para un CSV descargado desde S3 se debe leer y decodificar el contenido antes de pasarlo al parser correspondiente.

---

## 2026-08-29 - Identidad de clientes, PENDING y doble ejecución en Streamlit

### Contexto

Durante el review del flujo individual se revisaron la identificación de clientes existentes, la generación de clientes nuevos y el comportamiento frente a reruns o doble ejecución.

### Problema

Se identificaron tres riesgos:

- resolver clientes existentes utilizando silenciosamente la primera fila encontrada;
- generar un nuevo `PENDING-UUID` ante cada rerun de Streamlit;
- registrar dos veces una misma operación por doble clic o segunda ejecución.

### Causa

`Customer Full Name` no garantiza por sí solo una identidad única.

Además, Streamlit ejecuta nuevamente el script frente a diferentes interacciones, por lo que los identificadores creados directamente durante cada ejecución pueden cambiar si no se conservan en el estado de sesión.

### Solución aplicada

Para clientes existentes:

```text
nombre
→ buscar Customer ID asociados
→ si hay más de uno, seleccionar Customer ID exacto
→ recuperar datos del perfil
→ confirmar email
```

Los valores históricos de:

```text
Age
Gender
Location
Customer Email
```

se obtienen utilizando el valor válido más reciente y se advierten inconsistencias cuando corresponda.

Para clientes nuevos, el:

```text
PENDING-UUID
```

permanece estable durante toda la operación.

También se mantiene estable el `Transaction ID` de la operación y se bloquea una segunda ejecución de la misma venta dentro de la sesión.

### Resultado

El flujo deja de resolver identidades ambiguas mediante `.iloc[0]`.

Un mismo cliente nuevo conserva el mismo `PENDING-UUID` durante la operación y un doble submit no debe generar una segunda transacción.

La conversión:

```text
PENDING-UUID → CUSTXXXXXX
```

queda fuera de este PR y será responsabilidad de un consolidador nocturno desarrollado en una Issue separada.

### Prevención

Los campos descriptivos no deben reemplazar silenciosamente identificadores únicos.

Los identificadores necesarios durante una operación de Streamlit deben mantenerse en estado de sesión cuando deban sobrevivir a reruns.

Las operaciones de escritura deben diseñarse para tolerar reintentos sin generar duplicados lógicos.

---

## 2026-08-29 - Controles de consistencia e idempotencia en carga masiva

### Contexto

La carga masiva representa actualmente el ingreso manual de ventas provenientes del e-commerce mientras no exista una integración directa mediante API.

### Problema

Una carga podía superar la validación general del DataFrame sin cumplir reglas transaccionales necesarias para ser incorporada a staging.

También existía riesgo de reutilizar el resultado validado de un archivo anterior después de seleccionar otro archivo.

### Causa

Las reglas generales de calidad de datos no sustituyen las reglas específicas del flujo batch.

Además, Streamlit puede conservar información calculada previamente dentro de la sesión.

### Solución aplicada

Antes de permitir una carga se verifica:

- `Transaction ID` presente;
- `Transaction ID` no vacío;
- ausencia de `Transaction ID` duplicados dentro del mismo archivo;
- ausencia de `Transaction ID` ya presentes en el dataset canónico;
- canal `Online` válido;
- validación antes de la escritura en S3.

Un archivo idéntico no debe procesarse nuevamente como una nueva carga dentro de la misma operación.

Cuando cambia el archivo cargado, se invalida el `df_clean` correspondiente al archivo anterior y el nuevo archivo debe volver a validarse.

### Resultado

El flujo batch queda condicionado a reglas de integridad transaccional y canal antes de escribir en:

```text
staging/batch/
```

La reconciliación global contra todos los objetos existentes en staging no se implementa en este PR.

Esa responsabilidad corresponde al futuro consolidador nocturno.

### Prevención

Toda fuente batch debe validar no solamente estructura y tipos, sino también:

- identidad de transacciones;
- unicidad;
- canal de origen;
- reintentos;
- relación entre el archivo seleccionado y el resultado validado.

Las responsabilidades del flujo de ingreso y de la consolidación nocturna deben mantenerse separadas.