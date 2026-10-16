# RAG Evaluado: guía para Claude Code

Asistente RAG local que responde sobre documentos con citas y se abstiene si no hay evidencia, más un evaluador reproducible. Stack: Python 3.11, FastAPI, ChromaDB, sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`), Ollama (`qwen2.5:3b`), Docker Compose.

## Contexto y estado

- Lee `README.md` (resultados medidos y limitaciones) y `archivo.md` (bitácora técnica) antes de cambiar nada.
- Idioma: español para documentación y mensajes de commit.
- Corpus de evaluación: demo sintética sobre Orbe en `evals/` (35 casos: 29 respondibles, 6 sin respuesta).

## Comandos

```powershell
docker compose up -d --build                      # arrancar todo
docker compose exec ollama ollama pull qwen2.5:3b # primera vez
docker compose exec -T api python -m app.evaluation.runner --no-judge   # evaluación de 35 casos (varios minutos)
docker compose run --rm --no-deps --volume "${PWD}\tests:/workspace/tests:ro" api python -m unittest discover -s /workspace/tests -v
```

- Dashboard `http://localhost:8001/`, chat `http://localhost:8001/chat.html`, API `http://localhost:8000/docs`.
- `app/` está montado como volumen en la API: los cambios de código se aplican con `docker compose restart api`.

## Reglas de trabajo

- **Mide antes de afirmar.** Cambia una variable por pasada y compara sobre los mismos 35 casos. No presentes mejoras sin un informe en `reports/`.
- **No ejecutes dos evaluaciones a la vez** y revisa `run_state` en `/api/status` antes de lanzar una.
- **Mantén el corpus de evaluación limpio:** ningún documento personal indexado al evaluar (contamina las métricas). Tras una evaluación, restaura `app/static/project-status.json` si fue solo una prueba.
- Si modificas el índice de ChromaDB desde fuera de la API (por ejemplo con `docker compose exec`), reinicia la API; si no, `/api/ask` y `/api/evaluation/run` fallan con `'NoneType' object is not subscriptable`.
- Tras cada bloque importante actualiza `archivo.md` y, si cambian resultados o instrucciones, `README.md`.

## Seguridad y privacidad (no negociable)

- Los puertos 8000, 8001 y 11434 se publican solo en `127.0.0.1`. No los abras a `0.0.0.0`: Ollama y la API no tienen autenticación.
- No subas `data/` (documentos del usuario e índice), `.env*`, claves ni salidas locales; están en `.gitignore`.
- Antes de cualquier commit público: busca secretos, correos personales, teléfonos y rutas locales.
- No hagas `push` a un remoto sin que el usuario lo pida. No reescribas historial.
- Honestidad: este proyecto se desarrolló con asistencia de IA y el README lo declara. No inventes resultados ni afirmes que algo funciona sin haberlo ejecutado.

## Pendiente

Reducir las falsas abstenciones restantes (`top_k`, prompt, tamaño de fragmento, de uno en uno), pruebas de integración, GitHub Actions, autenticación si se expone fuera de localhost, licencia.
