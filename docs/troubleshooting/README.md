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