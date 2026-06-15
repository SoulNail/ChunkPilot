"""对 docs/ 下的文档做 RAG 灌库：结构感知切分 → GPU 向量化 → 写入 Qdrant。"""
import re
import uuid
from pathlib import Path

import torch
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# ---------- 配置 ----------
QDRANT_HOST = "192.168.110.51"
QDRANT_PORT = 6333
COLLECTION = "hermes_docs"
MODEL_NAME = "BAAI/bge-m3"
DOCS_DIR = Path(__file__).parent / "docs"

CHUNK_SIZE = 1000        # 每块目标字符数
CHUNK_OVERLAP = 150      # 块间重叠，避免切断语义
ENCODE_BATCH = 64        # GPU 编码批大小
UPSERT_BATCH = 256       # 写入 Qdrant 批大小

# 文档里每个源文件的分隔标记：====\nFILE: 路径\n====
FILE_MARKER = re.compile(r"^=+\nFILE: (.*?)\n=+\n", re.M)
# 递归切分时优先在这些边界断开（从大到小）
SEPARATORS = ["\n## ", "\n### ", "\n#### ", "\n\n", "\n", " "]


def split_into_files(text: str) -> list[tuple[str, str]]:
    """把拼接文档按 FILE 标记拆成 [(源文件路径, 内容), ...]。"""
    parts = FILE_MARKER.split(text)
    # parts = [前言, path1, content1, path2, content2, ...]
    out = []
    for i in range(1, len(parts), 2):
        path, content = parts[i].strip(), parts[i + 1].strip()
        if content:
            out.append((path, content))
    return out


def recursive_split(text: str, seps: list[str]) -> list[str]:
    """递归按分隔符切分到 <= CHUNK_SIZE。"""
    if len(text) <= CHUNK_SIZE:
        return [text]
    if not seps:
        # 没有分隔符可用，硬切
        return [text[i:i + CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]

    sep, rest = seps[0], seps[1:]
    pieces, buf = [], ""
    for seg in text.split(sep):
        candidate = seg if not buf else buf + sep + seg
        if len(candidate) <= CHUNK_SIZE:
            buf = candidate
        else:
            if buf:
                pieces.append(buf)
            # 单段仍超长 → 用更细的分隔符继续切
            pieces.extend(recursive_split(seg, rest) if len(seg) > CHUNK_SIZE else [seg])
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


def add_overlap(chunks: list[str]) -> list[str]:
    """给相邻块加重叠，提升跨块语义连续性。"""
    if CHUNK_OVERLAP <= 0 or len(chunks) <= 1:
        return chunks
    out = [chunks[0]]
    for prev, cur in zip(chunks, chunks[1:]):
        out.append(prev[-CHUNK_OVERLAP:] + cur)
    return out


def build_chunks() -> list[dict]:
    """读取 docs/ 下所有 .md，切分成带元数据的块。"""
    records = []
    for md in sorted(DOCS_DIR.glob("*.md")):
        raw = md.read_text(encoding="utf-8")
        files = split_into_files(raw) or [(md.name, raw)]  # 没有 FILE 标记则整篇处理
        for source, content in files:
            chunks = add_overlap(recursive_split(content, SEPARATORS))
            for idx, chunk in enumerate(chunks):
                chunk = chunk.strip()
                if len(chunk) < 20:        # 丢弃过短碎片
                    continue
                records.append({
                    "source": source,
                    "chunk_index": idx,
                    "doc": md.name,
                    "text": chunk,
                })
    return records


def main() -> None:
    print(f"读取并切分 {DOCS_DIR} ...")
    records = build_chunks()
    print(f"共得到 {len(records)} 个文本块")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"加载模型 {MODEL_NAME}（device={device}，首次会下载）...")
    model = SentenceTransformer(MODEL_NAME, device=device)
    dim = model.get_sentence_embedding_dimension()

    print(f"向量化（dim={dim}）...")
    vectors = model.encode(
        [r["text"] for r in records],
        batch_size=ENCODE_BATCH,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    print(f"连接 Qdrant {QDRANT_HOST}:{QDRANT_PORT} 并建库 '{COLLECTION}' ...")
    client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    client.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
    )

    print("分批写入 ...")
    for i in range(0, len(records), UPSERT_BATCH):
        batch_recs = records[i:i + UPSERT_BATCH]
        batch_vecs = vectors[i:i + UPSERT_BATCH]
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=v.tolist(), payload=r)
            for r, v in zip(batch_recs, batch_vecs)
        ]
        client.upsert(collection_name=COLLECTION, points=points)
        print(f"  已写入 {min(i + UPSERT_BATCH, len(records))}/{len(records)}")

    print(f"完成 ✅ collection='{COLLECTION}' 共 {len(records)} 个向量")


if __name__ == "__main__":
    main()
