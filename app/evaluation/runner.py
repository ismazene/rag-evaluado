import argparse
import asyncio
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import ollama

from app.config import settings
from app.retrieval.answer import answer_question
from app.retrieval.store import get_store

DEFAULT_DATASET = Path('evals/dataset.jsonl')
DEFAULT_REPORTS = Path('reports')
CORRECT_F1_THRESHOLD = 0.45


def normalize(text: str) -> str:
    text = unicodedata.normalize('NFD', text.lower())
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    return ' '.join(re.findall(r'[a-z0-9]+', text))


def token_f1(prediction: str, reference: str) -> float:
    predicted = Counter(normalize(prediction).split())
    expected = Counter(normalize(reference).split())
    if not predicted or not expected:
        return float(not predicted and not expected)
    common = sum((predicted & expected).values())
    precision = common / sum(predicted.values())
    recall = common / sum(expected.values())
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


async def judge_faithfulness(answer: str, citations: list[dict]) -> dict:
    if not citations:
        return {'faithful': False, 'reason': 'La respuesta no incluye citas.'}
    evidence = '\n\n'.join(f"[{item['id']}] {item['source']}, página {item['page']}: {item['text']}" for item in citations)
    prompt = (
        'Evalúa solo si cada afirmación factual de RESPUESTA está respaldada por la EVIDENCIA citada. '
        'No uses conocimiento externo ni premies que la respuesta coincida con una respuesta esperada. '
        'Devuelve JSON: {"faithful": true o false, "reason": "motivo breve en español"}. '
        'Si falta apoyo para una afirmación, faithful debe ser false.\n\n'
        f'RESPUESTA:\n{answer}\n\nEVIDENCIA:\n{evidence}'
    )
    response = await ollama.AsyncClient(host=settings.ollama_base_url).chat(
        model=settings.ollama_model,
        messages=[{'role': 'user', 'content': prompt}],
        format='json',
        options={'temperature': 0},
    )
    result = json.loads(response['message']['content'])
    return {'faithful': bool(result.get('faithful')), 'reason': str(result.get('reason', ''))[:240]}


def load_dataset(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def update_dashboard_run_state(state: str, error_type: str | None = None) -> None:
    status_path = Path('app/static/project-status.json')
    if not status_path.exists():
        return
    try:
        status = json.loads(status_path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError):
        return

    now = datetime.now().astimezone()
    evaluation = status.setdefault('evaluation', {})
    evaluation['run_state'] = state
    if state == 'running':
        evaluation['run_started_at'] = now.isoformat()
        status['current'] = {
            'title': 'Evaluación automática en curso',
            'state': 'En curso',
            'detail': 'Ollama procesa el conjunto de preguntas. El resultado aparecerá en el dashboard al terminar.',
        }
        event = 'Evaluación automática iniciada desde el proyecto.'
        stage_state = 'En curso'
        stage_detail = 'Runner activo; los resultados se guardarán al completar todos los casos.'
    else:
        evaluation['run_failed_at'] = now.isoformat()
        status['current'] = {
            'title': 'La evaluación no pudo completarse',
            'state': 'Error',
            'detail': 'El runner terminó con error '+str(error_type or 'desconocido')+'. Revisa los logs de la API.',
        }
        event = 'La evaluación terminó con error '+str(error_type or 'desconocido')+'.'
        stage_state = 'Pendiente'
        stage_detail = 'La última ejecución falló; no se añadió al historial.'
    status['updated_at'] = now.isoformat()
    activity = status.setdefault('activity', [])
    activity.insert(0, {'time': now.strftime('%H:%M'), 'text': event})
    status['activity'] = activity[:8]
    for stage in status.get('stages', []):
        if stage.get('name') == 'Evaluación y métricas':
            stage['state'] = stage_state
            stage['detail'] = stage_detail

    temporary = status_path.with_suffix('.json.tmp')
    try:
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(status_path)
    except OSError:
        temporary.unlink(missing_ok=True)

def update_project_status(metrics: dict) -> None:
    status_path = Path('app/static/project-status.json')
    if not status_path.exists():
        return
    try:
        status = json.loads(status_path.read_text(encoding='utf-8-sig'))
    except (OSError, json.JSONDecodeError):
        return

    threshold = float(settings.max_distance)
    generated_at = str(metrics.get('generated_at') or datetime.now(timezone.utc).isoformat())
    local_stamp = datetime.now().astimezone().strftime('%d/%m %H:%M')
    history = status.setdefault('evaluation', {}).setdefault('history', [])
    history.append({
        'name': f'Umbral {threshold:.2f} · {local_stamp}',
        'threshold': threshold,
        'accuracy_rate': metrics.get('accuracy_rate'),
        'answerable_mean_token_f1': metrics.get('answerable_mean_token_f1'),
        'citation_evidence_anchor_rate': metrics.get('citation_evidence_anchor_rate'),
        'false_abstention_rate_on_answerable': metrics.get('false_abstention_rate_on_answerable'),
    })
    summary_fields = (
        'total_cases', 'accuracy_rate', 'answerable_mean_token_f1',
        'citation_coverage', 'citation_evidence_anchor_rate',
        'faithfulness_judge_rate', 'faithfulness_judged_count',
        'unsupported_answer_rate_on_unanswerable', 'correct_abstention_rate',
        'false_abstention_rate_on_answerable', 'model',
    )
    summary = status['evaluation']
    for key in summary_fields:
        summary[key] = metrics.get(key)
    summary['judge'] = 'not run' if not metrics.get('faithfulness_judged_count') else 'run'
    summary['run_state'] = 'completed'
    summary['run_finished_at'] = datetime.now().astimezone().isoformat()
    status['current'] = {
        'title': 'Evaluación completada · resultados actualizados',
        'state': 'En curso',
        'detail': 'La pasada terminó. Se guardaron las métricas y el dashboard ya compara esta ejecución con las anteriores.',
    }
    for stage in status.get('stages', []):
        if stage.get('name') == 'Evaluación y métricas':
            stage['state'] = 'Completado'
            stage['detail'] = f"{metrics.get('total_cases', 0)} casos medidos con umbral {threshold:.2f}; informe guardado en reports/latest.json."
    summary['history'] = history
    status['updated_at'] = datetime.now().astimezone().isoformat()

    activity = status.setdefault('activity', [])
    activity.insert(0, {
        'time': datetime.now().astimezone().strftime('%H:%M'),
        'text': (
            f"Evaluación guardada: umbral {threshold:.2f}, "
            f"acierto {metrics.get('accuracy_rate', 0):.1%}, "
            f"falsas abstenciones {metrics.get('false_abstention_rate_on_answerable', 0):.1%}."
        ),
    })
    status['activity'] = activity[:8]

    temporary = status_path.with_suffix('.json.tmp')
    try:
        temporary.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(status_path)
    except OSError:
        temporary.unlink(missing_ok=True)

async def run_evaluation(dataset_path: Path = DEFAULT_DATASET, use_judge: bool = True) -> dict:
    record_dashboard = dataset_path.resolve() == DEFAULT_DATASET.resolve()
    if record_dashboard:
        update_dashboard_run_state('running')
    try:
        metrics = await _run_evaluation(dataset_path, use_judge)
    except Exception as exc:
        if record_dashboard:
            update_dashboard_run_state('failed', type(exc).__name__)
        raise
    if record_dashboard:
        update_project_status(metrics)
    return metrics

async def _run_evaluation(dataset_path: Path = DEFAULT_DATASET, use_judge: bool = True) -> dict:
    cases = load_dataset(dataset_path)
    store = get_store()
    results = []
    for case in cases:
        passages = store.search(case['question'], settings.top_k)
        response = await answer_question(case['question'], passages)
        abstained = bool(response['abstained'])
        should_abstain = bool(case['should_abstain'])
        answer_f1 = None if should_abstain else token_f1(response['answer'], case['reference_answer'])
        correct = abstained == should_abstain if should_abstain else (not abstained and answer_f1 >= CORRECT_F1_THRESHOLD)
        citation_text = normalize(' '.join(item['text'] for item in response['citations']))
        evidence_terms = case.get('evidence_terms', [])
        evidence_covered = all(normalize(term) in citation_text for term in evidence_terms) if evidence_terms and not should_abstain else None
        judge = None
        if use_judge and not abstained:
            try:
                judge = await judge_faithfulness(response['answer'], response['citations'])
            except Exception as exc:
                judge = {'faithful': None, 'reason': f'Error del juez: {type(exc).__name__}'}
        results.append({
            'id': case['id'], 'question': case['question'], 'answer': response['answer'],
            'reference_answer': case['reference_answer'], 'should_abstain': should_abstain,
            'abstained': abstained, 'correct': bool(correct), 'answer_token_f1': answer_f1,
            'citation_count': len(response['citations']), 'evidence_terms_covered': evidence_covered,
            'faithfulness_judge': judge,
            'citations': [{'source': item['source'], 'page': item['page'], 'text': item['text']} for item in response['citations']],
        })

    answerable = [row for row in results if not row['should_abstain']]
    unanswerable = [row for row in results if row['should_abstain']]
    answered = [row for row in answerable if not row['abstained']]
    judged = [row['faithfulness_judge'] for row in results if row['faithfulness_judge'] is not None and row['faithfulness_judge']['faithful'] is not None]
    anchored = [row for row in answerable if row['evidence_terms_covered'] is not None]
    def rate(numerator: int, denominator: int) -> float | None:
        return round(numerator / denominator, 4) if denominator else None

    metrics = {
        'total_cases': len(results),
        'accuracy_rate': rate(sum(row['correct'] for row in results), len(results)),
        'answerable_mean_token_f1': round(sum(row['answer_token_f1'] for row in answerable) / len(answerable), 4) if answerable else None,
        'citation_coverage': rate(sum(row['citation_count'] > 0 for row in answered), len(answered)),
        'citation_evidence_anchor_rate': rate(sum(row['evidence_terms_covered'] for row in anchored), len(anchored)),
        'faithfulness_judge_rate': rate(sum(item['faithful'] for item in judged), len(judged)),
        'faithfulness_judged_count': len(judged),
        'unsupported_answer_rate_on_unanswerable': rate(sum(not row['abstained'] for row in unanswerable), len(unanswerable)),
        'correct_abstention_rate': rate(sum(row['abstained'] for row in unanswerable), len(unanswerable)),
        'false_abstention_rate_on_answerable': rate(sum(row['abstained'] for row in answerable), len(answerable)),
        'correctness_rule': f"An answerable response is correct when token F1 >= {CORRECT_F1_THRESHOLD}; an unanswerable response is correct when it abstains.",
        'faithfulness_note': 'The local Ollama model judges its own answers, so this score is a useful signal, not an independent ground truth.',
        'generated_at': datetime.now(timezone.utc).isoformat(),
        'model': settings.ollama_model,
        'results': results,
    }
    DEFAULT_REPORTS.mkdir(parents=True, exist_ok=True)
    (DEFAULT_REPORTS / 'latest.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    (DEFAULT_REPORTS / f'evaluation-{stamp}.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')
    return metrics


async def main() -> None:
    parser = argparse.ArgumentParser(description='Evalúa respuestas del asistente RAG contra un conjunto JSONL.')
    parser.add_argument('--dataset', type=Path, default=DEFAULT_DATASET)
    parser.add_argument('--no-judge', action='store_true', help='No pedir a Ollama el juicio auxiliar de fidelidad.')
    args = parser.parse_args()
    report = await run_evaluation(args.dataset, use_judge=not args.no_judge)
    print(json.dumps({key: value for key, value in report.items() if key != 'results'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
