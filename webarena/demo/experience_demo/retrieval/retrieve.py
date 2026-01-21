from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from .embedder import Embedder
from .index import Experience, ExperienceIndex


@dataclass(frozen=True)
class RetrievedExperience:
	experience: Experience
	score: float


def retrieve_top_k(
	query: str,
	index: ExperienceIndex,
	embedder: Embedder,
	top_k: int = 3,
	site: Optional[str] = None,
) -> List[RetrievedExperience]:
	if not query or top_k <= 0:
		return []

	experiences = index.experiences
	embeddings = index.embeddings

	if site:
		mask = np.array([e.site == site for e in experiences], dtype=bool)
		if mask.any():
			experiences = [e for e in experiences if e.site == site]
			embeddings = embeddings[mask]

	q_vec = embedder.embed([query])
	if q_vec.size == 0:
		return []

	q = q_vec[0]
	scores = embeddings @ q
	k = min(top_k, int(scores.shape[0]))
	if k <= 0:
		return []

	top_idx = np.argpartition(-scores, kth=k - 1)[:k]
	top_idx = top_idx[np.argsort(-scores[top_idx])]

	return [
		RetrievedExperience(experience=experiences[i], score=float(scores[i]))
		for i in top_idx.tolist()
	]
