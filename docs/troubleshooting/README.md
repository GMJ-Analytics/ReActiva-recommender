# Solución de problemas

Este documento registra problemas técnicos relevantes encontrados durante el desarrollo de ReActiva, junto con su causa, la solución aplicada, el resultado y una medida preventiva.

Cada registro mantiene la estructura:

- Fecha
- Contexto
- Problema
- Causa
- Solución aplicada
- Resultado
- Prevención

El objetivo es conservar decisiones y aprendizajes técnicos sin mezclar en el README principal estados históricos u opciones que ya no forman parte de la arquitectura vigente.

---

## 2026-08-12 - PR con cambios de una tarea anterior

### Contexto

Durante la revisión de un Pull Request se detectó que la branch utilizada contenía código de una tarea anterior que el equipo había decidido no integrar.

### Problema

El PR incluía cambios ajenos a la tarea actual y existía riesgo de incorporarlos accidentalmente a `main`.

### Causa

Se reutilizó una branch previa en lugar de comenzar la nueva tarea desde `main` actualizado.

### Solución aplicada

Se revisó el diff antes del merge, se cerró el PR sin integrarlo y se descartó la branch correspondiente.

### Resultado

El código no deseado no llegó a `main`.

### Prevención

Mantener el flujo:

```text
Issue
→ main actualizado
→ branch propia
→ desarrollo
→ Pull Request
→ revisión
→ merge
→ eliminación de branch
```

No reutilizar branches de tareas anteriores.

---

## 2026-08-17 - requirements.txt con codificación incorrecta y dependencias AWS incompatibles

### Contexto

Durante la preparación del entorno compartido se revisó el `requirements.txt` canónico.

### Problema

El archivo se encontraba en UTF-16 y existían versiones AWS que debían mantenerse compatibles entre sí.

### Causa

El archivo había sido guardado con una codificación distinta de UTF-8 y las dependencias AWS poseen restricciones cruzadas.

### Solución aplicada

Se normalizó `requirements.txt` a UTF-8 y se validó el conjunto de dependencias relacionadas con AWS.

Entre las versiones comprobadas se encontraron:

```text
aiobotocore==3.9.0
boto3==1.43.56
botocore==1.43.56
s3fs==2026.7.0
fsspec==2026.7.0
```

### Resultado

`requirements.txt` volvió a ser interpretable normalmente por Git y por las herramientas de instalación.

La comprobación:

```bash
python -m pip check
```

finalizó sin dependencias rotas.

### Prevención

Mantener `requirements.txt` en UTF-8 y, después de modificar dependencias, ejecutar:

```bash
python -m pip install -r requirements.txt
python -m pip check
```

Las dependencias AWS deben revisarse de forma conjunta.

---

## 2026-08-18 - Archivo de origen en S3 incompatible con su extensión

### Contexto

Durante la preparación de datos se intentó cargar el dataset principal desde Amazon S3.

### Problema

La lectura fallaba con un error de decodificación al tratar el objeto como CSV.

### Causa

El contenido almacenado no era compatible con el formato indicado por la extensión `.csv`.

### Solución aplicada

Se reemplazó/corrigió el objeto almacenado en S3 y se validó nuevamente mediante la función oficial de carga.

### Resultado

El dataset volvió a quedar disponible para auditoría, validación, EDA y modelado.

En esa etapa se verificaron:

- 10.000 filas;
- 3.291 clientes únicos;
- `Customer Full Name` presente;
- `Customer Email` presente;
- `Frequency of Purchases` ausente.

Posteriormente el esquema canónico evolucionó hasta las 28 columnas vigentes con incorporación de `Customer Phone`.

### Prevención

Después de reemplazar un dataset en S3:

- comprobar formato real y extensión;
- validar lectura con la función oficial;
- revisar dimensiones y columnas;
- no continuar con el pipeline si la fuente no fue validada.

---

## 2026-08-18 - Eliminación incorrecta de transacciones legítimas por deduplicación

### Contexto

Se revisó la lógica de limpieza utilizada para detectar duplicados.

### Problema

Una clave basada en:

```text
Customer ID + Item Purchased + Purchase Date
```

podía eliminar compras legítimas realizadas por el mismo cliente sobre el mismo producto y fecha.

### Causa

La identidad única de una operación es:

```text
Transaction ID
```

Dos operaciones pueden coincidir en cliente, producto y fecha y seguir siendo transacciones diferentes.

### Solución aplicada

La validación del dataset pasó a considerar `Transaction ID` como identidad transaccional.

La clave histórica:

```text
duplicate_key_rows
```

se conservó por compatibilidad, pero representa duplicados de `Transaction ID`.

Los registros completamente idénticos pueden limpiarse como duplicados exactos, mientras que una colisión de `Transaction ID` debe tratarse como un problema de integridad.

### Resultado

Las compras legítimas con distintos `Transaction ID` dejaron de eliminarse incorrectamente.

### Prevención

Toda modificación futura de deduplicación debe comprobar:

- `Transaction ID` vacío;
- `Transaction ID` repetido;
- mismo cliente/producto/fecha con IDs distintos;
- registros distintos con el mismo ID.

---

## 2026-08-24 - Duplicación de dependencias y lógica del recomendador

### Contexto

Durante la integración de Streamlit, Docker y modelado se encontraron implementaciones duplicadas.

### Problema

Existían:

```text
requirements.txt
app/requirements.txt
```

y también:

```text
app/recommender.py
src/reactiva/recommender/recommender.py
```

Esto podía hacer que distintos componentes ejecutaran versiones diferentes.

### Causa

Los componentes habían evolucionado inicialmente de forma independiente.

### Solución aplicada

Se dejó como fuente canónica de dependencias:

```text
requirements.txt
```

en la raíz, y como fuente canónica de recomendación:

```text
src/reactiva/recommender/recommender.py
```

Los consumidores fueron actualizados para utilizar esas implementaciones.

### Resultado

El proyecto quedó con una única fuente reutilizable para dependencias y recomendación.

### Prevención

Antes de crear una nueva implementación, comprobar si esa responsabilidad ya existe en `src/reactiva`.

---

## 2026-08-24 - Runtime de Docker incompatible con el tipo de aplicación

### Contexto

La aplicación interactiva existente es Streamlit, aunque el entorno contenía dependencias relacionadas con una futura API.

### Problema

Existía riesgo de iniciar `app.py` como si fuera una aplicación ASGI mediante Uvicorn.

### Causa

Coexistían dependencias de etapas diferentes del proyecto.

### Solución aplicada

El Dockerfile de la aplicación quedó configurado para ejecutar Streamlit sobre el puerto 8501.

### Resultado

La aplicación pudo ejecutarse de forma coherente con su framework real.

### Prevención

El runtime de un contenedor debe corresponder al entrypoint realmente implementado.

Una futura API debe disponer de su propio módulo y no reemplazar accidentalmente el runtime de Streamlit.

---

## 2026-08-26 - Rutas locales absolutas en Power BI

### Contexto

Las consultas iniciales del proyecto Power BI apuntaban directamente a rutas de la computadora donde se creó el dashboard.

### Problema

Otro integrante no podía abrir y refrescar el proyecto desde otra ubicación sin editar múltiples consultas.

### Causa

Power BI creó referencias absolutas al importar CSV locales.

### Solución aplicada

Se creó el parámetro:

```text
RutaDatosBI
```

como ruta base para `dashboard/data`.

### Resultado

La ubicación local quedó centralizada en un único parámetro.

### Prevención

Toda nueva fuente local de Power BI debe depender de `RutaDatosBI` y no contener rutas personales hardcodeadas.

---

## 2026-08-26 / 2026-09-02 - Interpretación incorrecta de decimales por configuración regional en Power BI

### Contexto

Los CSV generados por Python utilizan punto como separador decimal.

El problema volvió a ser relevante al incorporar las salidas de monitoreo de Evidently.

### Problema

Power Query podía interpretar valores como:

```text
6065.5
```

de forma incorrecta.

En monitoreo, un valor como:

```text
0.20
```

también podía terminar interpretado de forma incompatible con la medida esperada.

### Causa

La configuración regional utilizada por Power BI no coincidía con el formato numérico de los CSV.

### Solución aplicada

Las conversiones numéricas sensibles se configuraron utilizando una configuración regional compatible con el punto decimal, particularmente `en-US` cuando correspondía.

### Resultado

Los importes, porcentajes y métricas de drift recuperaron sus valores correctos.

### Prevención

No depender únicamente de la inferencia automática de tipos de Power Query.

Validar manualmente decimales y porcentajes después de incorporar una nueva fuente CSV.

---

## 2026-08-28 - Incompatibilidad entre el modelo de reactivación y Streamlit

### Contexto

El flujo de reactivación había evolucionado hacia Gradient Boosting, pero Streamlit todavía conservaba lógica Customer-Customer.

### Problema

Streamlit utilizaba una estrategia User-Based que ya no correspondía con la arquitectura productiva.

### Causa

La lógica experimental anterior permanecía conectada al flujo operativo.

### Solución aplicada

Se separaron las responsabilidades:

```text
Cliente inactivo >= 270 días
→ Gradient Boosting
→ recomendación de reactivación
```

```text
Cliente existente Offline
→ producto comprado
→ Item-to-Item
→ recomendación
```

```text
Cliente nuevo Offline
→ producto comprado
→ Item-to-Item
→ recomendación
```

Las ventas Online se registran pero no generan recomendación en Streamlit.

### Resultado

User-Based / Customer-Customer dejó de formar parte del flujo productivo de Streamlit.

### Prevención

No mantener funciones experimentales conectadas al producto únicamente por compatibilidad histórica.

---

## 2026-08-28 - Cache indefinido del dataset histórico en Streamlit

### Contexto

Streamlit reutiliza el dataset histórico configurado mediante `DATASET_URI`.

### Problema

El cache no tenía expiración explícita y podía mantener una copia antigua aun después de actualizar S3.

### Causa

`st.cache_data` no disponía de `ttl`.

### Solución aplicada

Se configuró:

```python
@st.cache_data(ttl=3600)
```

### Resultado

El dataset puede reutilizarse durante una hora y luego vuelve a consultarse.

### Prevención

Toda fuente remota cacheada debe definir una política explícita de vigencia coherente con la necesidad de consistencia del negocio.

---

## 2026-08-28 - Separación de staging para ventas individuales y cargas masivas

### Contexto

Streamlit permite registrar ventas individuales y cargas masivas Online.

### Problema

Sin separación explícita resultaba difícil auditar el origen de cada archivo y aplicar reglas distintas.

### Solución aplicada

Se definieron:

```text
staging/individual/
staging/batch/
```

### Resultado

Las fuentes quedaron diferenciadas antes de su procesamiento posterior.

### Prevención

Toda nueva fuente de ingesta debe definir explícitamente su prefijo, formato, identidad, validaciones y proceso de consolidación.

---

## 2026-08-28 - Validación preventiva de carga masiva y robustez del visor de logs

### Contexto

Se revisaron defensas adicionales en el uploader CSV y en el visor administrativo de logs.

### Problema

Un archivo muy grande podía llegar a Pandas antes de validar tamaño.

El visor de logs suponía además que todos los registros contenían un `level` válido.

### Solución aplicada

Se definió un límite de:

```text
20 MB
```

en Streamlit y en la validación propia de la aplicación.

Para logs, los niveles ausentes o nulos se normalizan defensivamente como:

```text
UNKNOWN
```

y la lectura se mantiene acotada.

### Resultado

La carga masiva y el visor quedaron más resistentes a entradas inesperadas.

### Prevención

Separar validación del contenedor del archivo de validación del contenido.

Los visores operativos no deben asumir esquemas perfectos ni realizar lecturas ilimitadas.

---

## 2026-08-29 - Lectura incorrecta de CSV desde Amazon S3

### Contexto

Se revisó el helper de lectura de objetos S3.

### Problema

El stream `response["Body"]` se utilizaba sin parsear correctamente el CSV.

### Causa

El cuerpo de S3 es un stream de bytes, no un DataFrame.

### Solución aplicada

El flujo pasó a:

```text
leer Body
→ decodificar UTF-8
→ StringIO
→ pandas.read_csv()
```

### Resultado

Los objetos CSV descargados desde S3 se interpretan correctamente.

### Prevención

Procesar siempre un objeto descargado según su formato real antes de construir estructuras tabulares.

---

## 2026-08-29 - Identidad de clientes, PENDING y doble ejecución en Streamlit

### Contexto

Se revisó el flujo de clientes existentes, clientes nuevos y reruns de Streamlit.

### Problema

Existían riesgos de:

- resolver identidades usando la primera fila encontrada;
- regenerar `PENDING-UUID`;
- registrar dos veces una venta.

### Causa

El nombre no es una identidad única y Streamlit vuelve a ejecutar el script frente a interacciones.

### Solución aplicada

Para clientes existentes se utiliza `Customer ID` como identidad final.

Para clientes nuevos se conserva durante la operación:

```text
PENDING-UUID
Transaction ID
```

en estado de sesión.

También se incorporaron defensas frente a doble ejecución.

### Resultado

Las identidades y transacciones permanecen estables durante una operación.

### Prevención

No usar campos descriptivos como sustituto de identificadores únicos.

Las escrituras deben ser idempotentes frente a reintentos.

---

## 2026-08-29 - Controles de consistencia e idempotencia en carga masiva

### Contexto

La carga masiva representa ventas Online incorporadas manualmente.

### Problema

Un DataFrame podía superar controles generales sin cumplir reglas transaccionales específicas del batch.

También podía reutilizarse accidentalmente el resultado validado de un archivo anterior.

### Solución aplicada

Antes de persistir se valida:

- `Transaction ID` presente;
- ID no vacío;
- ausencia de IDs duplicados en el archivo;
- ausencia de IDs ya presentes en el dataset canónico;
- canal `Online`;
- correspondencia entre archivo cargado y resultado validado.

### Resultado

El batch queda condicionado a reglas transaccionales antes de escribir en `staging/batch/`.

### Prevención

Las validaciones de calidad general no reemplazan las reglas específicas de cada flujo de ingesta.

---

## 2026-08-31 - Columnas vacías de cupones interpretadas como float64 al leer desde S3

### Contexto

Los campos de redención de `campaign_active.csv` estaban inicialmente vacíos.

### Problema

Pandas podía inferir como `float64` columnas que posteriormente debían recibir texto:

```text
Coupon Redeemed At
Coupon Transaction ID
```

Al intentar registrar la redención aparecía un error de tipo.

### Causa

Una columna CSV completamente vacía no aporta información suficiente para que Pandas infiera que luego almacenará strings.

### Solución aplicada

Antes de escribir los nuevos valores, las columnas de seguimiento se convierten explícitamente a `object` dentro de la copia actualizada del DataFrame.

### Resultado

El cupón pudo marcarse como:

```text
REDEEMED
```

y asociarse a la transacción correspondiente.

### Prevención

Las columnas inicialmente vacías que posteriormente almacenarán timestamps o texto deben normalizar su dtype explícitamente.

---

## 2026-08-31 - Un fallo posterior en el cupón podía detener Streamlit después de registrar la venta

### Contexto

La venta se registra antes de persistir definitivamente el consumo del cupón.

### Problema

Si la venta ya estaba confirmada y luego fallaba el registro del cupón, `st.stop()` detenía también las responsabilidades posteriores del flujo.

### Causa

El manejo de errores no distinguía una validación previa a la venta de un fallo técnico posterior a una escritura ya confirmada.

### Solución aplicada

Se inicializa defensivamente:

```python
coupon_redemption = None
```

y un fallo posterior del cupón:

- se informa;
- se registra;
- conserva el `Transaction ID`;
- permite reintento idempotente;
- no detiene el resto del flujo.

### Resultado

Una venta confirmada puede continuar con la recomendación Item-to-Item aunque el subsistema de cupón necesite un reintento.

### Prevención

Los errores posteriores a una persistencia exitosa deben aislarse según la responsabilidad que falló.

---

## 2026-08-31 / 2026-09-02 - Restricciones de AWS por Permissions Boundary

### Contexto

Durante el desarrollo local no todos los integrantes disponían de permisos para administrar ECR, Lambda, EventBridge, SES o configuraciones relacionadas.

### Problema

La identidad AWS utilizada durante parte del desarrollo no podía ejecutar las operaciones necesarias para completar el despliegue.

### Causa

Existía una `Permissions Boundary` que limitaba los permisos efectivos.

Agregar una policy adicional al usuario no podía superar esa boundary.

### Solución aplicada

No se intentó eludir la restricción.

Se separaron responsabilidades:

```text
desarrollo y validación local
→ integrante que desarrolla

despliegue y configuración AWS
→ integrante autorizado
```

El despliegue final se continuó desde una identidad con permisos suficientes.

La arquitectura vigente de campañas ya no incluye la Lambda redundante `monthly_recommendations`.

Los componentes relevantes del cierre incluyen, entre otros:

```text
monthly_campaign
campaign_sender
unsubscribe
evidently_drift
consolidator
```

### Resultado

La restricción quedó tratada como un problema de infraestructura/permisos, no como un fallo funcional del código.

Los componentes pudieron continuar su configuración y validación en AWS por el integrante autorizado.

### Prevención

Antes de una tarea de infraestructura, comprobar permisos efectivos sobre los servicios necesarios y verificar también las Permissions Boundaries aplicables.

---

## 2026-09-01 - Campañas ejecutaban nuevamente el recomendador y generaban una segunda salida

### Contexto

Después de integrar inicialmente el subsistema de campañas se revisó la conexión entre el recomendador y `monthly_campaign`.

### Problema

La primera integración permitía que campañas volviera a ejecutar Gradient Boosting y generara una salida mensual propia.

Esto duplicaba una responsabilidad que ya pertenecía al recomendador canónico.

### Causa

Se había interpretado el flujo mensual como:

```text
campañas
→ ejecutar modelo
→ generar recomendaciones
→ crear campaña
```

cuando la arquitectura correcta debía separar ambos sistemas.

### Solución aplicada

Se restauró el recomendador a su responsabilidad anterior y se modificó:

```text
src/reactiva/campaigns/orchestrator.py
```

para consumir directamente el CSV ya producido por el recomendador.

El flujo vigente quedó:

```text
recomendador
→ CSV canónico de recomendaciones en S3
→ orchestrator
→ monthly_campaign
→ campaña/cupones/envíos
```

Se eliminó completamente:

```text
artifacts/AwsLambda/monthly_recommendations/
```

porque esa Lambda volvía a ejecutar GBoost de forma redundante.

También se eliminaron pruebas que pertenecían exclusivamente a esa arquitectura descartada.

### Resultado

Campañas dejó de entrenar o ejecutar nuevamente el modelo y pasó a consumir exclusivamente la salida canónica existente.

El recommender y las campañas quedaron desacoplados.

### Prevención

Cada componente debe tener una única responsabilidad.

Un consumidor de recomendaciones no debe volver a entrenar o ejecutar el modelo si la salida requerida ya existe como contrato entre sistemas.

---

## 2026-09-02 - campaign_sender falló por configuración incompleta de variables de entorno

### Contexto

Después del despliegue del sender en AWS se realizó una prueba controlada de la Lambda.

### Problema

La función llegó al código pero falló porque faltaba configuración obligatoria del servicio de mensajería.

Entre las variables requeridas por el sender se encuentran:

```text
SES_SENDER_EMAIL
UNSUBSCRIBE_BASE_URL
UNSUBSCRIBE_SECRET
```

La Lambda `unsubscribe` requiere también:

```text
UNSUBSCRIBE_SECRET
```

### Causa

Los valores son configuración de infraestructura y, deliberadamente, no están hardcodeados ni versionados en GitHub.

### Solución aplicada

Las variables se configuraron en el entorno de AWS.

El mismo `UNSUBSCRIBE_SECRET` debe utilizarse en:

```text
campaign_sender
unsubscribe
```

sin publicar su valor.

El remitente utilizado por SES debe ser una identidad configurada/verificada en Amazon SES.

### Resultado

La ejecución pudo avanzar desde un problema de configuración hacia la lógica funcional del sender.

### Prevención

Antes de probar una Lambda desplegada, revisar una checklist de variables obligatorias por componente.

Los secretos deben existir solamente en configuración segura de infraestructura, nunca en GitHub, capturas o documentación pública.

---

## 2026-09-02 - campaign_sender falló al escribir timestamps y errores sobre columnas float64

### Contexto

`campaign_active.csv` contiene columnas de seguimiento que pueden comenzar completamente vacías:

```text
Last Attempt At
Sent At
Reactivated At
Last Error
```

### Problema

Al leer el CSV, Pandas podía inferir estas columnas como `float64`.

Posteriormente el sender intentaba almacenar timestamps ISO o texto de error y producía una incompatibilidad de dtype.

### Causa

La inferencia automática de Pandas no conoce el tipo futuro de una columna que inicialmente contiene solamente valores vacíos.

### Solución aplicada

En:

```text
src/reactiva/campaigns/sender.py
```

después de copiar el DataFrame se normalizan esas columnas como `object` antes de realizar asignaciones:

```python
string_columns = [
    "Last Attempt At",
    "Sent At",
    "Reactivated At",
    "Last Error",
]

updated[string_columns] = (
    updated[string_columns]
    .astype("object")
)
```

No se modificó la lógica de envíos ni reintentos.

### Resultado

El hotfix fue integrado a `main`.

La Lambda actualizada pudo ejecutar el flujo sin el TypeError original.

La modificación puntual se validó mediante:

```bash
python -m py_compile src/reactiva/campaigns/sender.py
```

### Prevención

Los esquemas CSV con columnas inicialmente vacías deben tiparse explícitamente cuando esas columnas posteriormente recibirán texto o timestamps.

---

## 2026-09-02 - campaign_history.csv todavía no existía durante la primera campaña

### Contexto

Al preparar la página de campañas de Power BI se buscaron las fuentes disponibles en S3.

### Problema

La ruta:

```text
campaigns/campaign_history.csv
```

todavía no existía.

### Causa

La campaña vigente era el primer ciclo operativo disponible y aún no existía una campaña histórica cerrada que justificara ese archivo.

En cambio sí se encontraba disponible:

```text
campaigns/campaign_active.csv
```

con el estado actual del ciclo.

### Solución aplicada

La página de Reactivación y Campañas se conectó a:

```text
campaign_active.csv
```

para mostrar únicamente el estado real existente.

No se inventaron resultados históricos ni conversiones inexistentes.

### Resultado

Power BI pudo mostrar:

- clientes objetivo;
- estado de envío;
- programación por día;
- recomendaciones;
- cupones;
- reactivaciones y redenciones cuando existan.

### Prevención

Los consumidores BI deben tolerar que una salida histórica todavía no exista durante el primer ciclo de un proceso.

No debe interpretarse un archivo ausente como cero histórico sin entender previamente el estado operativo.

---

## 2026-09-02 - Necesidad de sincronizar S3 con Power BI sin rutas ni conexión directa frágil

### Contexto

Las nuevas páginas de campañas y monitoreo necesitan archivos producidos automáticamente en S3.

El proyecto Power BI debe seguir siendo portable y utilizable sin depender de Power BI Service.

### Problema

Mantener copias manuales de los CSV aumentaba el riesgo de mostrar información desactualizada.

Una conexión directa o rutas hardcodeadas tampoco coincidían con el esquema portable adoptado por el proyecto.

### Solución aplicada

Se creó:

```text
scripts/refresh_bi_data.py
```

para descargar y validar desde S3:

```text
monitoring/evidently/history/drift_summary_history.csv
monitoring/evidently/history/drift_features_history.csv
campaigns/campaign_active.csv
```

También se creó:

```text
actualizar_dashboard.bat
```

que ejecuta el script y abre el proyecto Power BI.

El flujo queda:

```text
.bat
→ Python
→ S3
→ validación
→ dashboard/data/
→ Power BI
→ Actualizar
```

### Resultado

Se validó una sincronización completa de las tres fuentes sin errores y Power BI pudo actualizarse con los datos descargados.

### Prevención

Centralizar toda sincronización externa del dashboard en un proceso reproducible y validar las fuentes antes de sobrescribir los archivos locales utilizados por BI.

---

## 2026-09-02 - Monitoreo de drift debía quedar desacoplado del entrenamiento

### Contexto

Se incorporó monitoreo de data drift con Evidently sobre features agregadas del cliente.

### Problema

Vincular automáticamente una señal de drift con reentrenamiento o bloqueo del recomendador habría agregado una decisión operativa no validada por el proyecto.

### Causa

Detectar drift y decidir reentrenar son responsabilidades diferentes.

Un cambio de distribución no implica por sí solo que el modelo haya perdido desempeño ni que deba bloquearse.

### Solución aplicada

El módulo:

```text
src/reactiva/monitoring/drift.py
```

se diseñó explícitamente desacoplado de:

- entrenamiento;
- generación de recomendaciones;
- campañas;
- orquestación AWS.

La ejecución operativa genera outputs estructurados e históricos en S3 para análisis y Power BI.

### Resultado

La primera ejecución real registrada evaluó cinco features y detectó drift en una.

El resumen fue:

```text
drifted_columns = 1
total_columns = 5
drift_share = 0.20
dataset_drift_threshold = 0.50
status = OK
```

La señal quedó disponible para monitoreo sin modificar automáticamente el modelo.

### Prevención

Toda automatización futura de reentrenamiento debe definirse como una decisión separada, con criterios adicionales y validación explícita.

---

## 2026-09-02 - Diferencia entre ejecución diaria del sender y clientes programados por día

### Contexto

Durante la configuración de AWS surgió la duda de cada cuánto debe ejecutarse `campaign_sender`.

### Problema

Podía confundirse la frecuencia de invocación de la Lambda con la distribución de clientes entre los días 1 a 5.

### Causa

La campaña asigna a cada cliente un `Scheduled Day`, pero el sender también necesita revisar reintentos que se habilitan después de 24 horas.

### Solución aplicada

El sender se diseñó como un proceso de ejecución diaria.

En cada corrida:

- carga `campaign_active.csv`;
- procesa únicamente filas `PENDING` que estén vencidas;
- para el primer intento exige que `Scheduled Day` coincida con el día actual;
- para reintentos exige al menos 24 horas desde el intento anterior;
- revalida inactividad antes de enviar.

### Resultado

La lógica permite mantener la distribución original de los días 1 a 5 y, al mismo tiempo, procesar reintentos sin crear un mecanismo separado.

### Prevención

Documentar por separado:

```text
frecuencia de ejecución del servicio
```

y:

```text
regla de elegibilidad de cada registro
```

para evitar confundir schedule de infraestructura con reglas de negocio.

---

# Criterio de mantenimiento

Al agregar nuevos incidentes:

1. documentar solamente problemas técnicos realmente observados;
2. distinguir estado histórico de arquitectura vigente;
3. retirar o corregir referencias a componentes eliminados;
4. no incluir secretos, tokens, credenciales ni valores privados;
5. indicar si una solución fue validada mediante compilación, tests o ejecución real;
6. evitar convertir este archivo en una segunda copia del README.

El README principal describe el estado actual de ReActiva.

Este documento conserva los problemas encontrados y las decisiones técnicas que permiten entender cómo se llegó a ese estado.
