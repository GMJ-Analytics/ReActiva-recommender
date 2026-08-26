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

Durante la validación de la limpieza reproducible de datos de la Issue #28 se revisó la regla utilizada para eliminar transacciones duplicadas.

### Problema

La lógica existente utilizaba como clave:

`Customer ID + Item Purchased + Purchase Date`

Con esa combinación se identificaban como duplicadas dos filas del dataset actual y eran eliminadas durante la limpieza, reduciendo incorrectamente la cantidad de transacciones.

### Causa

La clave utilizada no incluía `Transaction ID`. Un mismo cliente puede comprar el mismo producto más de una vez en la misma fecha y cada operación seguir siendo una transacción válida e independiente.

### Solución aplicada

Se incorporó `Transaction ID` a la clave utilizada para detectar duplicados:

`Transaction ID + Customer ID + Item Purchased + Purchase Date`

Además, si `Transaction ID` no está disponible, no se utiliza automáticamente la regla anterior de tres campos para eliminar filas.

Se agregaron tests automáticos para validar ambos escenarios.

### Resultado

Sobre el dataset actual:

- filas originales: 10.000;
- filas luego de la limpieza: 10.000;
- duplicados exactos eliminados: 0;
- duplicados por clave transaccional eliminados: 0.

También se validó que dos compras del mismo cliente, producto y fecha con distintos `Transaction ID` permanezcan como transacciones independientes.

### Prevención

Las reglas de deduplicación deben basarse en identificadores que permitan distinguir transacciones reales.

Toda modificación futura de la clave de deduplicación debe estar acompañada por tests que verifiquen al menos:

- transacciones distintas que comparten cliente, producto y fecha;
- duplicados reales con la misma clave transaccional;
- comportamiento cuando `Transaction ID` no está disponible.

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