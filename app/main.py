from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import router

app = FastAPI(
    title='RAG Evaluado',
    description='Asistente de documentos con respuestas citadas y evaluación de calidad.',
    version='0.1.0',
)
app.include_router(router, prefix='/api')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['http://localhost:8001', 'http://127.0.0.1:8001'],
    allow_methods=['GET', 'POST'],
    allow_headers=['*'],
)


@app.get('/health', tags=['estado'])
def health() -> dict[str, str]:
    return {'status': 'ok'}


app.mount('/', StaticFiles(directory='app/static', html=True), name='dashboard')
