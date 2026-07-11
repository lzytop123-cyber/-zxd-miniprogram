"""ChromaDB + RAG：多文档上传、切块、向量检索。"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
CHROMA_DIR = DATA_DIR / "chroma"
DOCS_DIR = DATA_DIR / "knowledge_docs"
REGISTRY_PATH = DATA_DIR / "knowledge_registry.json"
COLLECTION_NAME = "zhixingdao_kb"
MANUAL_DOC_ID = "manual"

_chroma_client = None
_collection = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def _load_registry() -> dict[str, Any]:
    _ensure_dirs()
    if not REGISTRY_PATH.is_file():
        return {"documents": []}
    try:
        return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("读取知识库索引失败: %s", exc)
        return {"documents": []}


def _save_registry(registry: dict[str, Any]) -> None:
    _ensure_dirs()
    REGISTRY_PATH.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rag_available() -> bool:
    return bool(settings.knowledge_rag_enabled and settings.assistant_configured)


def _get_collection():
    global _chroma_client, _collection
    if _collection is not None:
        return _collection
    try:
        import chromadb
    except ImportError as exc:
        raise RuntimeError("未安装 chromadb，请执行 pip install chromadb") from exc

    _ensure_dirs()
    _chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    _collection = _chroma_client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def chunk_text(text: str, *, chunk_size: int | None = None, overlap: int | None = None) -> list[str]:
    """按段落合并切块，尽量在句号/换行处断开。"""
    size = chunk_size or settings.knowledge_chunk_size
    ov = overlap or settings.knowledge_chunk_overlap
    text = re.sub(r"\r\n?", "\n", (text or "").strip())
    if not text:
        return []

    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]

    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) <= size:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(para) <= size:
            current = para
            continue
        start = 0
        while start < len(para):
            end = min(start + size, len(para))
            piece = para[start:end]
            if end < len(para):
                for sep in ("。", "！", "？", ".", "!", "?", "\n"):
                    idx = piece.rfind(sep)
                    if idx >= max(80, len(piece) // 3):
                        piece = piece[: idx + 1]
                        end = start + len(piece)
                        break
            chunks.append(piece.strip())
            if end >= len(para):
                current = ""
                break
            start = max(end - ov, start + 1)
        current = current or ""

    if current:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 DeepSeek OpenAI 兼容 embeddings 接口。"""
    if not texts:
        return []
    if not settings.assistant_configured:
        raise ValueError("未配置 DEEPSEEK_API_KEY，无法生成向量")

    base = settings.deepseek_base_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.deepseek_embedding_model,
        "input": texts,
    }
    try:
        with httpx.Client(timeout=settings.deepseek_timeout_sec) as client:
            resp = client.post(f"{base}/embeddings", headers=headers, json=payload)
        if resp.status_code >= 400:
            raise ValueError(f"Embedding 接口错误（{resp.status_code}）: {resp.text[:300]}")
        data = resp.json()
        rows = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
        return [row["embedding"] for row in rows]
    except httpx.HTTPError as exc:
        raise ValueError(f"Embedding 请求失败: {exc}") from exc


def _delete_doc_chunks(doc_id: str) -> None:
    collection = _get_collection()
    existing = collection.get(where={"doc_id": doc_id})
    ids = existing.get("ids") or []
    if ids:
        collection.delete(ids=ids)


def ingest_document(
    *,
    doc_id: str,
    text: str,
    filename: str,
    source: str = "upload",
    ext: str = "",
) -> dict[str, Any]:
    """切块、向量化并写入 Chroma。"""
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("文档没有可索引的内容")

    _delete_doc_chunks(doc_id)
    embeddings = embed_texts(chunks)
    if len(embeddings) != len(chunks):
        raise ValueError("向量数量与文本块不一致")

    collection = _get_collection()
    ids = [f"{doc_id}:{i}" for i in range(len(chunks))]
    metadatas = [
        {
            "doc_id": doc_id,
            "filename": filename,
            "source": source,
            "chunk_index": i,
            "chars": len(chunk),
        }
        for i, chunk in enumerate(chunks)
    ]
    collection.add(ids=ids, documents=chunks, embeddings=embeddings, metadatas=metadatas)

    record = {
        "id": doc_id,
        "filename": filename,
        "ext": ext,
        "source": source,
        "chars": len(text),
        "chunks": len(chunks),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    registry = _load_registry()
    docs = [d for d in registry.get("documents", []) if d.get("id") != doc_id]
    docs.insert(0, record)
    registry["documents"] = docs
    _save_registry(registry)
    return record


def delete_document(doc_id: str) -> bool:
    registry = _load_registry()
    docs = registry.get("documents", [])
    target = next((d for d in docs if d.get("id") == doc_id), None)
    if not target:
        return False

    _delete_doc_chunks(doc_id)
    if doc_id != MANUAL_DOC_ID:
        ext = target.get("ext") or ""
        raw_path = DOCS_DIR / f"{doc_id}{ext}"
        if raw_path.is_file():
            raw_path.unlink()

    registry["documents"] = [d for d in docs if d.get("id") != doc_id]
    _save_registry(registry)
    return True


def list_documents() -> list[dict[str, Any]]:
    return list(_load_registry().get("documents", []))


def get_document_record(doc_id: str) -> dict[str, Any] | None:
    return next((d for d in list_documents() if d.get("id") == doc_id), None)


def _preview_text_from_chunks(doc_id: str) -> str:
    try:
        collection = _get_collection()
        result = collection.get(where={"doc_id": doc_id}, include=["documents", "metadatas"])
    except Exception as exc:
        logger.warning("读取文档片段失败: %s", exc)
        return ""

    docs = result.get("documents") or []
    metas = result.get("metadatas") or []
    if not docs:
        return ""

    pairs = sorted(
        zip(docs, metas),
        key=lambda item: int((item[1] or {}).get("chunk_index") or 0),
    )
    return "\n\n".join(text for text, _ in pairs if text).strip()


def get_document_preview(doc_id: str, *, manual_loader) -> dict[str, Any]:
    """返回文档全文预览（优先原始文件，其次向量片段拼接）。"""
    record = get_document_record(doc_id)
    if not record:
        raise ValueError("文档不存在")

    content = ""
    preview_source = "chunks"

    if doc_id == MANUAL_DOC_ID or record.get("source") in ("manual", "legacy"):
        content = (manual_loader() or "").strip()
        preview_source = "manual"
    else:
        ext = record.get("ext") or ""
        raw_path = DOCS_DIR / f"{doc_id}{ext}"
        if raw_path.is_file():
            from app.services import assistant as assistant_service

            raw = raw_path.read_bytes()
            content = assistant_service.parse_knowledge_upload(raw, ext=ext).strip()
            preview_source = "file"

    if not content:
        content = _preview_text_from_chunks(doc_id)
        preview_source = "chunks"

    if not content:
        raise ValueError("文档没有可预览的内容")

    return {
        "document": record,
        "content": content,
        "chars": len(content),
        "preview_source": preview_source,
    }


def rag_stats() -> dict[str, Any]:
    try:
        collection = _get_collection()
        count = collection.count()
    except Exception:
        count = 0
    docs = list_documents()
    return {
        "enabled": rag_available(),
        "documents": len(docs),
        "chunks": count,
        "persist_dir": str(CHROMA_DIR),
    }


def retrieve_context(query: str, *, top_k: int | None = None) -> str:
    """按用户问题检索相关片段，拼成提示词上下文。"""
    q = (query or "").strip()
    if not q or not rag_available():
        return ""

    try:
        collection = _get_collection()
        if collection.count() == 0:
            return ""
        query_emb = embed_texts([q])[0]
        n = top_k or settings.knowledge_rag_top_k
        results = collection.query(
            query_embeddings=[query_emb],
            n_results=min(n, collection.count()),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        logger.warning("RAG 检索失败: %s", exc)
        return ""

    docs = results.get("documents") or [[]]
    metas = results.get("metadatas") or [[]]
    if not docs or not docs[0]:
        return ""

    lines: list[str] = []
    for i, (chunk, meta) in enumerate(zip(docs[0], metas[0]), start=1):
        filename = (meta or {}).get("filename") or "知识库"
        lines.append(f"[片段{i} · {filename}]\n{chunk}")
    return "\n\n".join(lines)


def sync_manual_document(text: str, *, filename: str = "手动编辑.md") -> dict[str, Any] | None:
    """同步后台手动编辑区到向量库。"""
    text = (text or "").strip()
    if not text:
        delete_document(MANUAL_DOC_ID)
        return None
    if not rag_available():
        return None
    return ingest_document(
        doc_id=MANUAL_DOC_ID,
        text=text,
        filename=filename,
        source="manual",
        ext=".md",
    )


def ingest_uploaded_file(*, filename: str, ext: str, raw: bytes, text: str) -> dict[str, Any]:
    if not rag_available():
        raise ValueError("RAG 未启用或未配置 DeepSeek API Key")

    doc_id = uuid.uuid4().hex
    _ensure_dirs()
    raw_path = DOCS_DIR / f"{doc_id}{ext}"
    raw_path.write_bytes(raw)
    return ingest_document(
        doc_id=doc_id,
        text=text,
        filename=filename,
        source="upload",
        ext=ext,
    )


def migrate_legacy_markdown_if_needed(load_markdown) -> None:
    """首次启用 RAG 时，把旧版单文件知识库导入向量库。"""
    if not rag_available():
        return
    registry = _load_registry()
    if registry.get("documents"):
        return
    try:
        if _get_collection().count() > 0:
            return
    except Exception:
        pass

    legacy = (load_markdown() or "").strip()
    if not legacy:
        return
    try:
        ingest_document(
            doc_id=MANUAL_DOC_ID,
            text=legacy,
            filename="默认知识库.md",
            source="legacy",
            ext=".md",
        )
        logger.info("已将 legacy 知识库导入 Chroma（%s 字）", len(legacy))
    except Exception as exc:
        logger.warning("legacy 知识库导入失败: %s", exc)
