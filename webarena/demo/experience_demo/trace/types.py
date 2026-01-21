from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class RetrievalTrace:
	query: str
	top_k: int
	model_name: str
	results: List[Dict[str, Any]]  # each: {id, score, summary, content, site, tags}


@dataclass
class StepTrace:
	step: int
	url: Optional[str]
	obs_excerpt: str
	prompt_user: str
	prompt_system: str
	llm_output: str
	action_text: str
	action_valid: bool
	error: Optional[str]
	screenshot_path: Optional[str]

