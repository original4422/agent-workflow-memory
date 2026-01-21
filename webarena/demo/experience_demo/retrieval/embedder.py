from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np
from sentence_transformers import SentenceTransformer


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
	if vectors.size == 0:
		return vectors.astype(np.float32)
	norms = np.linalg.norm(vectors, axis=1, keepdims=True)
	norms = np.where(norms == 0, 1.0, norms)
	return (vectors / norms).astype(np.float32)


@dataclass
class Embedder:
	model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
	device: Optional[str] = None

	_model: Optional[SentenceTransformer] = None

	def _get_model(self) -> SentenceTransformer:
		if self._model is None:
			self._model = SentenceTransformer(self.model_name, device=self.device)
		return self._model

	def embed(self, texts: Iterable[str], batch_size: int = 32) -> np.ndarray:
		texts_list = [t if t is not None else "" for t in texts]
		if not texts_list:
			return np.zeros((0, 0), dtype=np.float32)

		model = self._get_model()
		vectors = model.encode(
			texts_list,
			batch_size=batch_size,
			show_progress_bar=False,
			convert_to_numpy=True,
			normalize_embeddings=False,
		)
		vectors = np.asarray(vectors)
		return _normalize_rows(vectors)
