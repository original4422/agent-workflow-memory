# 经验库 embedding 索引构建与加载
# 仅为结构占位，后续补充完整实现
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .embedder import Embedder


@dataclass(frozen=True)
class Experience:
    id: str
    site: str
    tags: List[str]
    summary: str
    content: str
    query_hint: Optional[str] = None


@dataclass(frozen=True)
class ExperienceIndex:
    experiences: List[Experience]
    embeddings: np.ndarray  # shape: (N, D) normalized float32
    model_name: str


def _sha1_text(text: str) -> str:
    """Return the SHA1 hex digest of `text`."""
    return hashlib.sha1(text.encode("utf-8"), usedforsecurity=False).hexdigest()


def _summaries_fingerprint(experiences: List[Experience]) -> str:
    """Return a fingerprint for the current summaries (used for cache invalidation)."""
    joined = "\n".join([e.summary for e in experiences])
    return _sha1_text(joined)


def load_experiences_jsonl(path: Path) -> List[Experience]:
    """Load experiences from a JSON Lines file.

    Each line is expected to be a JSON object with keys:
    `id`, `site`, `tags`, `summary`, `content` (and optional `query_hint`).

    Args:
        path: Path to the JSONL file.

    Returns:
        A non-empty list of `Experience` objects.

    Raises:
        ValueError: If required keys are missing or the file is empty.
    """
    experiences: List[Experience] = []
    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            obj: Dict[str, Any] = json.loads(line)
            for key in ["id", "site", "tags", "summary", "content"]:
                if key not in obj:
                    raise ValueError(f"Missing key '{key}' in {path}: {obj}")
            experiences.append(
                Experience(
                    id=str(obj["id"]),
                    site=str(obj["site"]),
                    tags=list(obj.get("tags", [])),
                    summary=str(obj["summary"]),
                    content=str(obj["content"]),
                    query_hint=(str(obj["query_hint"]) if obj.get("query_hint") else None),
                )
            )
    if not experiences:
        raise ValueError(f"No experiences found in {path}")
    return experiences


def _cache_paths(experiences_path: Path, model_name: str) -> Tuple[Path, Path]:
    """Return cache paths for embeddings and metadata."""
    safe_model = model_name.replace("/", "__")
    cache_dir = experiences_path.parent / ".cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    emb_path = cache_dir / f"embeddings__{safe_model}.npy"
    meta_path = cache_dir / f"embeddings__{safe_model}.meta.json"
    return emb_path, meta_path


def _load_cache(meta_path: Path) -> Optional[Dict[str, Any]]:
    """Load metadata JSON if present and valid; otherwise return None."""
    if not meta_path.exists():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def build_or_load_index(
    experiences_path: Path,
    embedder: Embedder,
) -> ExperienceIndex:
    """Build an embedding index for experiences, reusing cache when possible.

    The cache is keyed by a fingerprint of the experience summaries and the
    embedding model name.

    Args:
        experiences_path: Path to the experiences JSONL.
        embedder: Embedder used to generate vectors.

    Returns:
        An `ExperienceIndex` containing experiences and their embeddings.
    """
    experiences = load_experiences_jsonl(experiences_path)
    fingerprint = _summaries_fingerprint(experiences)
    emb_path, meta_path = _cache_paths(experiences_path, embedder.model_name)

    meta = _load_cache(meta_path)
    if meta and meta.get("fingerprint") == fingerprint and meta.get("model_name") == embedder.model_name:
        if emb_path.exists():
            embeddings = np.load(emb_path)
            return ExperienceIndex(experiences=experiences, embeddings=embeddings.astype(np.float32), model_name=embedder.model_name)

    summaries = [e.summary for e in experiences]
    embeddings = embedder.embed(summaries)
    np.save(emb_path, embeddings)
    meta_path.write_text(
        json.dumps(
            {
                "model_name": embedder.model_name,
                "fingerprint": fingerprint,
                "n": len(experiences),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return ExperienceIndex(experiences=experiences, embeddings=embeddings, model_name=embedder.model_name)
