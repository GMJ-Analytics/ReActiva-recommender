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