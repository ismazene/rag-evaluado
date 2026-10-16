from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    documents_dir: str = 'data/documents'
    chroma_dir: str = 'data/chroma'
    embedding_model: str = 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
    ollama_base_url: str = 'http://ollama:11434'
    ollama_model: str = 'qwen2.5:3b'
    top_k: int = 5
    max_distance: float = 0.75
    chunk_size: int = 900
    chunk_overlap: int = 150


settings = Settings()
