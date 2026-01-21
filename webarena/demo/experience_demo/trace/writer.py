from __future__ import annotations

import base64
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
from PIL import Image

from .types import RetrievalTrace, StepTrace


def _json_default(obj: Any) -> Any:
	if isinstance(obj, Path):
		return str(obj)
	if isinstance(obj, (np.ndarray,)):
		return obj.tolist()
	return str(obj)


def save_screenshot_from_obs(obs: Dict[str, Any], screenshots_dir: Path, step: int) -> Optional[str]:
	screenshots_dir.mkdir(parents=True, exist_ok=True)
	out_path = screenshots_dir / f"step_{step:04d}.png"

	if obs is None:
		return None

	img = obs.get("screenshot")
	if img is None:
		img = obs.get("screenshot_bytes")
	if img is None:
		return None

	try:
		if isinstance(img, (bytes, bytearray)):
			out_path.write_bytes(bytes(img))
			return str(out_path)

		if isinstance(img, str):
			# best-effort base64 decode
			try:
				raw = base64.b64decode(img)
				out_path.write_bytes(raw)
				return str(out_path)
			except Exception:
				return None

		if isinstance(img, Image.Image):
			img.save(out_path)
			return str(out_path)

		if isinstance(img, np.ndarray):
			Image.fromarray(img).save(out_path)
			return str(out_path)

		return None
	except Exception:
		return None


class TraceWriter:
	def __init__(self, run_dir: Path):
		self.run_dir = run_dir
		self.run_dir.mkdir(parents=True, exist_ok=True)
		self.trace_path = self.run_dir / "trace.jsonl"
		self.summary_path = self.run_dir / "summary.json"
		self.screenshots_dir = self.run_dir / "screenshots"
		self._fp = self.trace_path.open("a", encoding="utf-8")

	def write_event(self, event_type: str, payload: Dict[str, Any]) -> None:
		record = {
			"ts": time.time(),
			"type": event_type,
			"payload": payload,
		}
		self._fp.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
		self._fp.flush()

	def log_retrieval(self, trace: RetrievalTrace) -> None:
		self.write_event("retrieval", asdict(trace))

	def log_step(self, trace: StepTrace) -> None:
		self.write_event("step", asdict(trace))

	def write_summary(self, summary: Dict[str, Any]) -> None:
		self.summary_path.write_text(
			json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
			encoding="utf-8",
		)

	def close(self) -> None:
		try:
			self._fp.close()
		except Exception:
			pass

