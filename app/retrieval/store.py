import hashlib
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from app.config import settings
from app.ingestion.chunking import TextChunk


class DocumentStore:
    def __init__(self) -> None:
        Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=settings.chroma_dir)
        self.embedding = SentenceTransformerEmbeddingFunction(model_name=settings.embedding_model)
        self.collection = self.client.get_or_create_collection(
            name='documents',
            embedding_function=self.embedding,
            metadata={'hnsw:space': 'cosine'},
        )

    def add(self, chunks: list[TextChunk]) -> int:
        if not chunks:
            return 0
        ids = [hashlib.sha256(f'{item.source}:{item.page}:{item.index}:{item.text}'.encode()).hexdigest() for item in chunks]
        self.collection.upsert(
            ids=ids,
            documents=[item.text for item in chunks],
            metadatas=[{'source': item.source, 'page': item.page, 'index': item.index} for item in chunks],
        )
        return len(chunks)

    def search(self, question: str, limit: int) -> list[dict]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(query_texts=[question], n_results=min(limit, self.collection.count()))
        documents = result['documents'][0]
        metadatas = result['metadatas'][0]
        distances = result['distances'][0]
        return [
            {'id': f'S{index + 1}', 'text': text, 'source': metadata['source'], 'page': metadata['page'], 'distance': distance}
            for index, (text, metadata, distance) in enumerate(zip(documents, metadatas, distances))
            if distance <= settings.max_distance
        ]


_store: DocumentStore | None = None


def get_store() -> DocumentStore:
    global _store
    if _store is None:
        _store = DocumentStore()
    return _store
