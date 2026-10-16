# Diario y estado de RAG Evaluado

Este es el registro de continuidad del proyecto. Léelo antes de modificar código. El usuario pidió autonomía, documentación persistente y que el dashboard muestre el avance para no tener que preguntar por el estado.

Última actualización: 14 de octubre de 2026, 18:33 (Europe/Madrid).

## Objetivo y preferencias del usuario

- Construir un asistente RAG local que responda sobre documentos, cite evidencia y mida aciertos, abstenciones e invenciones.
- Mantener README.md para presentación pública y este archivo como bitácora técnica completa.
- Hacer un dashboard visual e interactivo: el agente principal es el jefe; cada delegado tiene nombre, rol y oficina. Las consultas reales deben representarse con un recorrido por el pasillo.
- El usuario quiere preparar el proyecto para publicarlo en GitHub como portfolio propio. Conservar atribución correcta: dirección del proyecto del usuario, con asistencia de Codex y agentes de IA; nunca ocultar aportaciones ni inventar resultados.
- Hablar en español, actuar autónomamente y actualizar el dashboard y los MD con cambios importantes para que no tenga que preguntar cómo va.

## Carpeta y servicios

- Trabaja sobre la carpeta `rag-evaluado` abierta como raíz del workspace. Windows redirige su Escritorio a OneDrive; no supongas que la carpeta `Desktop` es la visible ni uses una copia duplicada.
- Dashboard: http://localhost:8001/
- Chat RAG: http://localhost:8001/chat.html
- API docs: http://localhost:8000/docs
- API health: http://localhost:8000/health
- Estado API: http://localhost:8000/api/status
- Compose tiene Nginx para el dashboard en 8001, FastAPI en 8000 y Ollama en 11434.

Comandos básicos desde la raíz:

```powershell
docker compose ps
docker compose up -d --build
docker compose down
```

Los datos de documentos e índice están bajo `data/`; `ollama_data` y `huggingface_cache` son volúmenes persistentes. No incluir documentos privados, modelos descargados ni rutas personales en archivos públicos.

## Stack y comportamiento

- Python 3.11 en Docker, FastAPI, ChromaDB persistente, `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` y Ollama con `qwen2.5:3b`.
- Chunking: 900 caracteres con solapamiento de 150. `top_k=5`; umbral Chroma de cosine distance ahora en 0.75.
- Se admiten PDF, TXT y Markdown. La respuesta usa solo pasajes recuperados, valida IDs de cita y se abstiene si no tiene evidencia.
- Endpoints principales: `POST /api/documents`, `POST /api/ask`, `POST /api/evaluation/run`, `GET /api/evaluation/latest`, `GET /api/status`.
- El documento de demo y las 35 preguntas hablan de Orbe, un servicio completamente ficticio.

## Lo implementado

### Chat web

- `app/static/chat.html`: subida de PDF/TXT/MD, preguntas, historial visible en la página y citas con fuente, página y extracto.
- Se comprobó `GET http://localhost:8001/chat.html`: HTTP 200. Usa `POST /api/documents` y `POST /api/ask` con los formatos esperados.

### Dashboard

- `app/static/index.html` sirve como panel de seguimiento y se actualiza cada 10 segundos desde `/api/status`, con JSON estático de respaldo.
- Muestra etapas, actividad reciente, servicios, recuento de agentes activos a partir del estado real de cada oficina, oficinas seleccionables y enlaces directos a chat y API. Tras terminar las tareas de esta sesión, marca 0 activos y 3 tareas terminadas.
- Equipo actual: Codex (jefe de RAG y orquestación), Vega (Frontend/UX) y Ada (QA/evaluación). Solo contar como activos a los que estén trabajando de verdad; las tareas terminadas se etiquetan como tales.
- Codex aparece como bolita azul. Los empleados tienen oficinas. El último mensaje registrado entre Ada y Codex sobre cuál copia local era la activa se reproduce por el pasillo. Los controles permiten pausar/reanudar y repetir ese recorrido.
- El intercambio mostrado sale de `agents.latest_interaction` en `app/static/project-status.json`. No hay integración automática del navegador con la herramienta interna de colaboración: Codex debe registrar allí los intercambios reales que llegan por mensajes de colaboración. No inventar preguntas ni hacer pasar una animación de demo por actividad real.
- La evaluación permite elegir entre acierto, F1, evidencia en citas y falsas abstenciones. El botón `Ejecutar evaluación (35 casos)` llama a la API con `use_judge=false` y muestra que está en curso.
- `app/evaluation/runner.py` marca inicio/fallo/fin en el JSON y agrega al historial cada evaluación estándar. Solo sincroniza el dashboard cuando el dataset es `evals/dataset.jsonl`; los tests que usan un dataset temporal no deben contaminar la actividad ni el historial.
- El historial inicial tiene las mediciones 0.45 y 0.75; ejecuciones futuras estándar deben añadirse automáticamente.

### Evaluador y pruebas

- `evals/dataset.jsonl`: 35 preguntas (29 respondibles, 6 no respondibles).
- `app/evaluation/runner.py` calcula F1, acierto, cobertura de citas, evidencia, abstenciones y respuestas no sustentadas; informes en `reports/latest.json` y archivo fechado.
- `tests/test_ingestion_chunking.py`: cuatro pruebas de fragmentación. `tests/test_evaluation_metrics.py`: cuatro pruebas de normalización/F1/abstención con store y generación simulados.
- Ada ejecutó previamente las ocho desde el directorio real `tests/`, montado en modo de solo lectura en el contenedor; resultado 8 OK. Comando equivalente:

```powershell
docker compose run --rm --no-deps --volume <ruta-absoluta-a-tests>:/workspace/tests:ro api python -m unittest discover -s /workspace/tests -v
```

El usuario de este proyecto no quiere informes falsos: las pruebas son unitarias y offline. No prueban recuperación real, ingesta integral, embeddings, Ollama ni una evaluación RAG completa.

## Evaluación real y calibración

Ambas pasadas usaron el mismo modelo, corpus y 35 preguntas; la variable modificada fue el umbral de distancia máxima de recuperación.

| Métrica | Umbral 0.45 | Umbral 0.75 |
| --- | ---: | ---: |
| Acierto global | 22.86 % (8/35) | 34.29 % (12/35) |
| F1 medio respondible | 5.27 % | 21.29 % |
| Evidencia de referencia presente en las citas | 6.90 % | 44.83 % |
| Falsas abstenciones en 29 respondibles | 93.10 % (27/29) | 55.17 % (16/29) |
| Abstención correcta en 6 sin respuesta | 100 % (6/6) | 100 % (6/6) |
| Respuesta sin apoyo en casos sin respuesta | 0 % (0/6) | 0 % (0/6) |

Regla de acierto: pregunta respondible correcta si token F1 >= 0.45; caso sin respuesta correcto si el asistente se abstiene. El umbral 0.75 mejoró recuperación y citas, pero el resultado general sigue siendo insuficiente: 16 de 29 preguntas respondibles aún se rechazan. No presentar como éxito final.

El juez auxiliar no se ejecutó. No existe todavía una medición independiente de fidelidad. La cobertura de citas del 100 % usa como denominador solo las respuestas no abstencionistas; no debe mostrarse sin esa explicación.

Informes registrados: baseline `reports/evaluation-20261014-155930.json`, prueba `reports/evaluation-20261014-161534.json`, alias más reciente `reports/latest.json`. `.gitignore` deja versionados `latest.json` y esos dos informes; informes fechados nuevos quedan ignorados hasta revisar.

## Comprobaciones

En esta sesión (incluido el ajuste final del contador de agentes activos): el script embebido del dashboard pasó `node --check`; `app/evaluation/runner.py` pasó `python -m py_compile`; GET del dashboard, chat y estado API devolvieron HTTP 200. Estas comprobaciones no sustituyen una inspección visual manual en navegador.

Ada volvió a ejecutar las ocho pruebas después de integrar el seguimiento de las evaluaciones: **8 correctas**. Revisó también dos veces que una ejecución con dataset temporal deja intactos el hash y fecha de `project-status.json`, el historial (2 filas), el dataset real y la lista de informes. No ejecutó la evaluación lenta de 35 casos. En la primera comprobación instantánea el archivo coincidió con una actualización simultánea legítima de Codex; la segunda comprobación quedó estable.

## Equipo y delegación

- Codex — jefe de proyecto; recuperación RAG, dashboard y documentación de relevo. Tarea de esta sesión terminada.
- Vega — Frontend/UX; terminó e integró la página de chat. HTTP 200 comprobado.
- Ada — QA/evaluación; revisión final del runner completada y ocho pruebas offline correctas.

Los agentes delegados pertenecen a esta sesión y podrían no sobrevivir al cambio de cuenta. En la nueva cuenta, comprobar qué agentes existen y no afirmar que Vega/Ada siguen activos si no es así. El recuento de `project-status.json` debe corresponder a tareas reales.

## Publicación y transparencia

- README.md está redactado en español para GitHub: arquitectura, instalación, API, resultados comparados, límites, pruebas, roles, autoría y asistencia de IA.
- El README no contiene la ruta personal del equipo. Tampoco `project-status.json` ni el texto visible del dashboard.
- No hay workflow de GitHub Actions ni remoto confirmado. No afirmar que CI esté verde, que exista un repositorio remoto o que el proyecto se haya publicado.
- El dueño quiere publicar el proyecto como portfolio propio; documentar Codex/Vega/Ada como asistencia de IA de manera clara.
- No subir datos privados. No borrar la copia local duplicada sin identificar exactamente el destino.

## Estado para continuar

- El traspaso está listo. El dashboard refleja las tareas terminadas, 0 delegados activos y el estado de evaluación completado.
- El chat ya existe y está servido; dashboard/API respondieron HTTP 200 en la comprobación reciente.
- Comparación 0.45 vs 0.75 guardada en informes, status y README.
- El botón de evaluación y la sincronización de historial están integrados; Ada revisó el runner y confirmó 8 pruebas correctas y que los datasets temporales no contaminan el estado.
- `README.md` es la presentación pública, `archivo.md` contiene el historial técnico de continuidad y `PROMPT_CONTINUACION.md` contiene instrucciones listas para pegar en otra cuenta.
- No se hizo inspección visual con navegador ni se ejecutó otra evaluación de 35 casos en este cierre.

## Siguientes pasos técnicos

1. Comprobar `docker compose ps` y abrir el dashboard/chat; hacer una inspección visual de oficinas, recorrido Ada→Codex, selector, replay/pausa y botón de evaluación.
2. Si se necesita validar el flujo end-to-end del botón, iniciar una única evaluación estándar y esperar su fin; primero revisar `run_state` y no lanzar evaluaciones concurrentes porque la pasada de 35 casos tarda varios minutos.
3. Mejorar recuperación de forma controlada: cambiar top_k, prompt o chunking de uno en uno y evaluar siempre sobre los mismos casos.
4. Añadir fuentes públicas con licencia clara y preguntas revisadas por persona; después ampliar las pruebas de integración.
5. Preparar GitHub Actions para las ocho pruebas y comprobar `.gitignore`; no publicar ni hacer push sin solicitud explícita.
6. Añadir captura/GIF y completar decisión de licencia antes de publicación.

## Reglas para retomar

1. Leer `README.md`, este archivo, `PROMPT_CONTINUACION.md` y `app/static/project-status.json`.
2. Confirmar que la raíz actual es el proyecto `rag-evaluado`, inspeccionar `docker compose ps` y consultar los endpoints. No empezar desde cero.
3. No ejecutar en paralelo una segunda evaluación local pesada. Mira el `run_state`, los informes y el historial primero.
4. Tras cada bloque importante, actualiza `project-status.json`, README si cambia lo publicable y este diario.
5. Mantén visibles los límites, el resultado actual y quién está realmente trabajando. No esperes a que el usuario pregunte cómo va.

## Sesión 2026-10-16 (Claude Code)

- Docker Desktop estaba apagado; se arrancó (`%LOCALAPPDATA%\Programs\DockerDesktop`). `docker compose up -d --build` levantó api, ollama y dashboard. `qwen2.5:3b` ya estaba descargado.
- Verificado: dashboard (8001), chat.html, /health y /api/status responden 200. `POST /api/ask` con "Que es Orbe?" devuelve respuesta correcta con cita de `manual_demo.md`.
- Nota: desde Git Bash, enviar JSON con acentos en línea da "error parsing the body"; usar archivo con `--data-binary`.
- Siguiente: mejorar recuperación cambiando una variable por pasada (primero top_k 5 -> 8) y comparar con los mismos 35 casos.
- Graphify ejecutado sobre el proyecto: graphify-out/graph.html (interactivo), GRAPH_REPORT.md y graph.json. 130 nodos, 216 aristas, 12 comunidades. Etiquetas de comunidad automáticas (no curadas).
- Corregido 404 en chat.html: llamaba a /api/* en el puerto 8001 (nginx estatico). Ahora usa http://localhost:8000/api/* (CORS ya habilitado en la API), igual que el dashboard.
- CORS de la API ampliado a GET y POST (el chat hace POST desde 8001). API reiniciada y preflight verificado.
- Corregido bug de citas en app/retrieval/answer.py: el modelo a veces devolvia 'citaciones' en lugar de 'citations' y se trataba como abstencion. Ahora se acepta esa variante y las citas [S#] del texto.
- Evaluacion 35 casos (reports/evaluation-20261016-151656.json): acierto 42,86 %, F1 30,88 %, evidencia en citas 51,72 %, falsas abstenciones 31,03 %, abstencion correcta 6/6, sin apoyo 0/6. Mejora parcial; no es calidad de produccion.
- Seguridad: puertos 8000/8001/11434 limitados a 127.0.0.1 en compose.yaml; .gitignore ampliado (.env*, claves, graphify-out, PROMPT_CONTINUACION.md). README reescrito como documentacion de ingenieria.
- Project Hub generico creado fuera del repo en C:\Users\Ismael\project-hub (localStorage + export/import JSON).
- Reevaluacion limpia (solo corpus Orbe, sin PDF privado en el indice; reports/evaluation-20261016-152118.json): acierto 45,71 % (16/35), F1 36,04 %, evidencia 68,97 %, falsas abstenciones 24,14 % (7/29), abstencion correcta 6/6, sin apoyo 0/6. La medicion anterior (42,86 %) estaba contaminada por un PDF privado indexado y no se publica.
- Pruebas en navegador real (Chrome headless con Playwright): chat (pregunta, subida de archivo, pregunta sobre el archivo subido), dashboard (pausa/reanudar, repetir consulta, selector de metrica, boton de evaluacion completo) y consola sin errores. Se corrigio: 404 de favicon, texto obsoleto "pendiente de primera ingesta", entrada contaminada (42,9 %) del historial y referencia a PROMPT_CONTINUACION.md.
- Nota operativa: si se modifica el indice ChromaDB desde otro proceso (docker exec) hay que reiniciar la API; si no, /api/evaluation/run falla con 'NoneType' object is not subscriptable.
- Capturas del chat y del dashboard anadidas en docs/ y enlazadas en el README; seccion de operacion y resolucion de problemas.
- Anadido CLAUDE.md con comandos, reglas de trabajo y seguridad para retomar el proyecto en sesiones nuevas.
