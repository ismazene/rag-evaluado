import json
import re

import ollama

from app.config import settings

UNKNOWN_ANSWER = 'No lo sé con los documentos disponibles.'


async def answer_question(question: str, passages: list[dict]) -> dict:
    if not passages:
        return {'answer': UNKNOWN_ANSWER, 'citations': [], 'abstained': True}

    context = '\n\n'.join(f"[{item['id']}] ({item['source']}, página {item['page']}): {item['text']}" for item in passages)
    prompt = (
        'Responde en español usando exclusivamente el CONTEXTO. No completes huecos con conocimiento externo. '
        'Si no hay evidencia suficiente, responde exactamente: No lo sé con los documentos disponibles. '
        'Toda afirmación debe llevar una cita como [S1]. Devuelve JSON con las claves answer y citations; '
        'citations debe ser una lista de identificadores usados (por ejemplo ["S1"]).\n\n'
        f'CONTEXTO:\n{context}\n\nPREGUNTA: {question}'
    )
    client = ollama.AsyncClient(host=settings.ollama_base_url)
    response = await client.chat(
        model=settings.ollama_model,
        messages=[{'role': 'user', 'content': prompt}],
        format='json',
        options={'temperature': 0},
    )
    payload = json.loads(response['message']['content'])
    answer = str(payload.get('answer', '')).strip()
    valid_ids = {item['id'] for item in passages}
    # El modelo pequeño a veces escribe 'citaciones' o solo pone [S1] en el texto.
    raw = payload.get('citations') or payload.get('citaciones') or []
    raw = list(raw) if isinstance(raw, list) else []
    raw += re.findall(r'S\d+', answer)
    cited_ids = list(dict.fromkeys(item for item in raw if item in valid_ids))
    if not answer or answer == UNKNOWN_ANSWER or not cited_ids:
        return {'answer': UNKNOWN_ANSWER, 'citations': [], 'abstained': True}
    citations = [
        {'id': item['id'], 'source': item['source'], 'page': item['page'], 'text': item['text']}
        for item in passages if item['id'] in cited_ids
    ]
    return {'answer': answer, 'citations': citations, 'abstained': False}
