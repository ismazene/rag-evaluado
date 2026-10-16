import json
from pathlib import Path

import ollama
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.config import settings
from app.evaluation.runner import run_evaluation
from app.ingestion.chunking import chunk_document
from app.retrieval.answer import answer_question
from app.retrieval.store import get_store

router = APIRouter()
STATUS_FILE = Path(__file__).resolve().parents[1] / 'static' / 'project-status.json'


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=2000)


class EvaluationRequest(BaseModel):
    use_judge: bool = True


@router.get('/status', tags=['estado'])
async def project_status() -> dict:
    status = json.loads(STATUS_FILE.read_text(encoding='utf-8-sig'))
    status['runtime'] = {'api': True, 'ollama': False, 'model_installed': False, 'models': []}
    try:
        available = await ollama.AsyncClient(host=settings.ollama_base_url).list()
        names = [model.model for model in available.models]
        status['runtime'].update(
            ollama=True,
            model_installed=settings.ollama_model in names,
            models=names,
        )
    except Exception:
        pass
    return status


@router.get('/demo-document', tags=['demo'])
def demo_document() -> FileResponse:
    path = Path('evals/manual_demo.md')
    if not path.exists():
        raise HTTPException(status_code=404, detail='Aún no hay documento de demostración.')
    return FileResponse(path, filename='manual_demo.md', media_type='text/markdown')


@router.post('/documents', tags=['documentos'])
async def upload_document(file: UploadFile = File(...)) -> dict:
    filename = Path(file.filename or '').name
    if Path(filename).suffix.lower() not in {'.pdf', '.txt', '.md'}:
        raise HTTPException(status_code=415, detail='Formato no admitido. Usa PDF, TXT o MD.')
    destination = Path(settings.documents_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / filename
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail='El archivo está vacío.')
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail='El límite por archivo es 20 MB.')
    path.write_bytes(content)
    try:
        chunks = chunk_document(path)
        count = get_store().add(chunks)
    except Exception as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f'No se pudo procesar el documento: {exc}') from exc
    return {'filename': filename, 'chunks_indexed': count}


@router.post('/ask', tags=['preguntas'])
async def ask(request: AskRequest) -> dict:
    try:
        passages = get_store().search(request.question, settings.top_k)
        return await answer_question(request.question, passages)
    except ollama.ResponseError as exc:
        raise HTTPException(status_code=503, detail=f'Ollama no pudo generar la respuesta: {exc.error}') from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f'No se pudo completar la consulta. Comprueba que Ollama esté activo y tenga el modelo configurado: {exc}') from exc


@router.post('/evaluation/run', tags=['evaluación'])
async def evaluate(request: EvaluationRequest) -> dict:
    try:
        return await run_evaluation(use_judge=request.use_judge)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f'No se pudo ejecutar la evaluación: {exc}') from exc


@router.get('/evaluation/latest', tags=['evaluación'])
def latest_evaluation() -> dict:
    path = Path('reports/latest.json')
    if not path.exists():
        raise HTTPException(status_code=404, detail='Aún no hay una evaluación guardada.')
    return json.loads(path.read_text(encoding='utf-8-sig'))
