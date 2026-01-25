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
    """Best-effort JSON serializer for non-primitive objects."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj)


def save_screenshot_from_obs(obs: Dict[str, Any], screenshots_dir: Path, step: int) -> Optional[str]:
    """Persist a screenshot from an environment observation.

    Supports multiple common screenshot formats:
    - bytes / bytearray
    - base64-encoded string
    - PIL Image
    - numpy array

    Args:
        obs: Observation dict.
        screenshots_dir: Directory where screenshots will be stored.
        step: Step index used for filename formatting.

    Returns:
        The screenshot path as a string, or `None` if unavailable.
    """
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
    def __init__(self, log_dir: Path):
        """Create a JSONL trace writer under `log_dir`."""
        self._log_dir = log_dir
        self.dir = log_dir / "trace" 
        self.dir.mkdir(parents=True, exist_ok=True)
        self.trace_path = self.dir / "trace.jsonl"
        self.summary_path = self.dir / "summary.json"
        self.screenshots_dir = self.dir / "screenshots"
        self._fp = self.trace_path.open("a", encoding="utf-8")

    def write_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Append a typed event record to the JSONL trace."""
        record = {
            "ts": time.time(),
            "type": event_type,
            "payload": payload,
        }
        self._fp.write(json.dumps(record, ensure_ascii=False, default=_json_default) + "\n")
        self._fp.flush()

    def log_retrieval(self, trace: RetrievalTrace) -> None:
        """Log a retrieval event."""
        self.write_event("retrieval", asdict(trace))

    def log_step(self, trace: StepTrace) -> None:
        """Log a step event."""
        self.write_event("step", asdict(trace))

    def write_summary(self, summary: Dict[str, Any]) -> None:
        """Write a summary JSON file for the run."""
        self.summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default),
            encoding="utf-8",
        )

    def close(self) -> None:
        """Close the underlying trace file handle."""
        try:
            self._fp.close()
        except Exception:
            pass

