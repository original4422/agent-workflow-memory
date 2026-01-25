"""Unit tests for retrieval.

These tests avoid heavy dependencies (e.g. sentence-transformers downloads) by
using a small fake embedder with deterministic vectors.
"""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Iterable

import numpy as np

# Ensure the repo root is on sys.path so `import experience_demo_2.*` works when
# running this file directly.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from retrieval.index import Experience, ExperienceIndex
from retrieval.retrieve import retrieve_top_k


@dataclass
class FakeEmbedder:
    """A deterministic embedder for tests."""

    model_name: str = "fake"
    query_vec: np.ndarray = field(
        default_factory=lambda: np.array([1.0, 0.0], dtype=np.float32)
    )

    def embed(self, texts: Iterable[str], batch_size: int = 32) -> np.ndarray:
        texts_list = list(texts)
        if not texts_list:
            return np.zeros((0, 0), dtype=np.float32)
        # Return one vector per input text.
        return np.stack([self.query_vec.astype(np.float32) for _ in texts_list], axis=0)


class RetrievalTests(unittest.TestCase):
    def _make_index(self) -> ExperienceIndex:
        experiences = [
            Experience(id="e1", site="shopping_admin", tags=["t"], summary="s1", content="c1"),
            Experience(id="e2", site="shopping_admin", tags=["t"], summary="s2", content="c2"),
            Experience(id="e3", site="shopping_admin", tags=["t"], summary="s3", content="c3"),
            Experience(id="e4", site="other", tags=["t"], summary="s4", content="c4"),
        ]

        # Pre-normalized 2D embeddings so dot product equals cosine similarity.
        embeddings = np.array(
            [
                [1.0, 0.0],
                [0.9, 0.1],
                [-1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=np.float32,
        )
        # Normalize rows defensively.
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        embeddings = embeddings / np.where(norms == 0, 1.0, norms)

        return ExperienceIndex(experiences=experiences, embeddings=embeddings, model_name="fake")

    def test_empty_query_returns_empty(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder()
        self.assertEqual(retrieve_top_k("", index=index, embedder=embedder, top_k=3), [])

    def test_non_positive_top_k_returns_empty(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder()
        self.assertEqual(retrieve_top_k("q", index=index, embedder=embedder, top_k=0), [])
        self.assertEqual(retrieve_top_k("q", index=index, embedder=embedder, top_k=-1), [])

    def test_ranking_is_descending(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder(query_vec=np.array([1.0, 0.0], dtype=np.float32))

        results = retrieve_top_k("q", index=index, embedder=embedder, top_k=3)
        ids = [r.experience.id for r in results]

        self.assertEqual(ids[:2], ["e1", "e2"])
        self.assertTrue(results[0].score >= results[1].score >= results[2].score)

    def test_top_k_larger_than_n(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder()

        results = retrieve_top_k("q", index=index, embedder=embedder, top_k=999)
        self.assertEqual(len(results), len(index.experiences))

    def test_site_filter_keeps_only_matching(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder()

        results = retrieve_top_k("q", index=index, embedder=embedder, top_k=10, site="shopping_admin")
        self.assertTrue(all(r.experience.site == "shopping_admin" for r in results))

    def test_site_filter_no_match_returns_empty(self) -> None:
        index = self._make_index()
        embedder = FakeEmbedder()

        results = retrieve_top_k("q", index=index, embedder=embedder, top_k=3, site="does_not_exist")
        self.assertEqual(results, [])

    def test_empty_embedding_from_embedder_returns_empty(self) -> None:
        index = self._make_index()

        class EmptyEmbedder(FakeEmbedder):
            def embed(self, texts: Iterable[str], batch_size: int = 32) -> np.ndarray:
                return np.zeros((0, 0), dtype=np.float32)

        results = retrieve_top_k("q", index=index, embedder=EmptyEmbedder(), top_k=3)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
