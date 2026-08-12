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

`Issue → branch propia desde main actualizado → desarrollo → Pull Request → revisión → merge → eliminación de la branch`

Cada nueva tarea debe trabajarse en una branch independiente para evitar arrastrar cambios de trabajos anteriores.
