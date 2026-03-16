"""Embedding generation using sentence-transformers with lazy model loading.

Supports MOCK_MODE: generates deterministic pseudo-random vectors from text hash
so that similar texts produce similar (but not identical) vectors.
"""

from __future__ import annotations

import hashlib
import logging
import math
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
_model_lock = threading.Lock()

EMBEDDING_DIM = 384


def _mock_embedding(text: str) -> list[float]:
    """Generate a deterministic pseudo-random embedding from text hash."""
    h = hashlib.sha512(text.lower().encode()).digest()
    raw = []
    for i in range(EMBEDDING_DIM):
        byte_idx = i % len(h)
        raw.append((h[byte_idx] + i * 7) % 256 / 255.0 * 2 - 1)
    norm = math.sqrt(sum(x * x for x in raw))
    if norm > 0:
        raw = [x / norm for x in raw]
    return raw


def _get_model() -> SentenceTransformer:
    """Return the sentence-transformers model, loading it lazily (thread-safe singleton)."""
    global _model
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from sentence_transformers import SentenceTransformer as _ST

            settings = get_settings()
            logger.info("Loading embedding model: %s", settings.rag_embedding_model)
            _model = _ST(settings.rag_embedding_model)
            logger.info("Embedding model loaded successfully")
            return _model
        except ImportError:
            logger.error(
                "sentence-transformers not installed. "
                "Install it or use MOCK_MODE=true"
            )
            raise
        except Exception as e:
            logger.error("Failed to load embedding model: %s", e)
            raise


def get_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Input text must not be empty")

    settings = get_settings()
    if settings.mock_mode:
        return _mock_embedding(text)

    model = _get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def get_embeddings(texts: list[str]) -> list[list[float]]:
    if not texts:
        raise ValueError("Input texts list must not be empty")

    cleaned = []
    for i, t in enumerate(texts):
        if not t or not t.strip():
            raise ValueError(f"Text at index {i} is empty")
        cleaned.append(t.strip())

    settings = get_settings()
    if settings.mock_mode:
        return [_mock_embedding(t) for t in cleaned]

    model = _get_model()
    embeddings = model.encode(cleaned, normalize_embeddings=True, batch_size=32)
    return [emb.tolist() for emb in embeddings]


def build_endpoint_text(endpoint: dict) -> str:
    """Build a searchable text representation of an API endpoint.

    Combines method, path, summary, description, and parameter names
    into a single string for embedding.
    """
    parts: list[str] = []

    method = endpoint.get("method", "").upper()
    path = endpoint.get("path", "")
    if method and path:
        parts.append(f"{method} {path}")

    summary = endpoint.get("summary", "")
    if summary:
        parts.append(summary)

    description = endpoint.get("description", "")
    if description:
        parts.append(description)

    tags = endpoint.get("tags", [])
    if tags:
        parts.append("Tags: " + ", ".join(tags))

    parameters = endpoint.get("parameters", [])
    if parameters:
        param_names = []
        for p in parameters:
            name = p.get("name", "")
            if name:
                param_names.append(name)
        if param_names:
            parts.append("Parameters: " + ", ".join(param_names))

    return " | ".join(parts) if parts else ""
