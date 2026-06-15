"""后端配置。开发期默认值面向当前拓扑；Docker 部署用环境变量覆盖。"""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RAG_", env_file=".env")

    # 嵌入来源：api = 调 110.3 GPU 服务；local = 后端进程内跑 BGE-M3+reranker（N100 CPU）
    embedding_mode: str = "api"          # "api" | "local"
    # 110.3 上的 GPU 推理服务；开发在本机则用 localhost，Docker 部署改为 http://192.168.110.3:8001
    embedding_service_url: str = "http://localhost:8001"
    # local 模式用的模型名
    local_embed_model: str = "BAAI/bge-m3"
    local_rerank_model: str = "BAAI/bge-reranker-v2-m3"
    # Qdrant；Docker 内用 http://qdrant:6333
    qdrant_url: str = "http://192.168.110.51:6333"

    docs_dir: Path = Path(__file__).resolve().parent.parent.parent / "docs"
    data_dir: Path = Path(__file__).resolve().parent.parent / "data"

    embed_batch: int = 64       # 调推理服务时的分批大小
    request_timeout: float = 120.0

    @property
    def db_path(self) -> Path:
        return self.data_dir / "app.db"


settings = Settings()
settings.docs_dir.mkdir(parents=True, exist_ok=True)
settings.data_dir.mkdir(parents=True, exist_ok=True)
