"""检索：把问题向量化后在 Qdrant 里找最相近的块。

用法: uv run search.py "你的问题" [top_k]
"""
import sys

import torch
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

QDRANT_HOST = "192.168.110.51"
QDRANT_PORT = 6333
COLLECTION = "hermes_docs"
MODEL_NAME = "BAAI/bge-m3"   # 必须与灌库时同一模型


def main() -> None:
    if len(sys.argv) < 2:
        print('用法: uv run search.py "你的问题" [top_k]')
        sys.exit(1)
    query = sys.argv[1]
    top_k = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)
    qvec = model.encode(query, normalize_embeddings=True).tolist()

    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    hits = client.query_points(
        collection_name=COLLECTION,
        query=qvec,
        limit=top_k,
        with_payload=True,
    ).points

    print(f"\n问题: {query}\n" + "=" * 60)
    for rank, h in enumerate(hits, 1):
        p = h.payload
        print(f"\n#{rank}  score={h.score:.4f}  来源: {p['source']}")
        print("-" * 60)
        print(p["text"][:300].strip())


if __name__ == "__main__":
    main()
