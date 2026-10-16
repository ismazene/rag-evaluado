from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from app.config import settings


@dataclass
class TextChunk:
    text: str
    source: str
    page: int
    index: int


def read_document(path: Path) -> list[tuple[int, str]]:
    suffix = path.suffix.lower()
    if suffix == '.pdf':
        return [(number, page.extract_text() or '') for number, page in enumerate(PdfReader(path).pages, start=1)]
    if suffix in {'.txt', '.md'}:
        return [(1, path.read_text(encoding='utf-8-sig'))]
    raise ValueError('Formato no admitido. Sube un archivo PDF, TXT o MD.')


def split_text(text: str, size: int | None = None, overlap: int | None = None) -> list[str]:
    size = size if size is not None else settings.chunk_size
    overlap = overlap if overlap is not None else settings.chunk_overlap
    if size < 1 or overlap < 0 or overlap >= size:
        raise ValueError('El tamaño del fragmento debe ser positivo y el solapamiento menor que el tamaño.')
    cleaned = ' '.join(text.split())
    if not cleaned:
        return []
    step = size - overlap
    return [cleaned[start:start + size] for start in range(0, len(cleaned), step)]


def chunk_document(path: Path) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    index = 0
    for page_number, text in read_document(path):
        for part in split_text(text):
            chunks.append(TextChunk(text=part, source=path.name, page=page_number, index=index))
            index += 1
    return chunks
