from __future__ import annotations

import base64
import contextvars
import datetime
import glob
import hashlib
import json
import os
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple


_SCHEMA_VERSION = "1.0"

_STEP_IDX: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar("step_idx", default=None)
_CALL_IDX: contextvars.ContextVar[int] = contextvars.ContextVar("call_idx", default=0)


def set_step_idx(step_idx: int) -> None:
	_STEP_IDX.set(int(step_idx))


def get_step_idx() -> Optional[int]:
	return _STEP_IDX.get()


def reset_call_idx() -> None:
	_CALL_IDX.set(0)


def next_call_idx() -> int:
	current = int(_CALL_IDX.get())
	_CALL_IDX.set(current + 1)
	return current


def _now_iso() -> str:
	return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _get_exp_dir() -> Optional[str]:
	exp_dir = os.environ.get("WEBARENA_EXP_DIR")
	if not exp_dir:
		return None
	return exp_dir


def _tmp_jsonl_path(exp_dir: str) -> str:
	pid = os.getpid()
	return os.path.join(exp_dir, f"conversation_history.{pid}.jsonl.tmp")


def _final_json_path(exp_dir: str) -> str:
	return os.path.join(exp_dir, "conversation_history.json")


def _images_dir(exp_dir: str) -> str:
	return os.path.join(exp_dir, "images")


def _sha256_bytes(data: bytes) -> str:
	return hashlib.sha256(data).hexdigest()


_DATA_URL_RE = re.compile(r"^data:(?P<media_type>[^;]+);base64,(?P<b64>.+)$")


def _decode_data_url(data_url: str) -> Optional[Tuple[str, bytes]]:
	match = _DATA_URL_RE.match(data_url or "")
	if not match:
		return None
	media_type = match.group("media_type")
	b64 = match.group("b64")
	try:
		raw = base64.b64decode(b64, validate=False)
	except Exception:
		return None
	return media_type, raw


def _ext_for_media_type(media_type: str) -> str:
	mt = (media_type or "").lower().strip()
	if mt.endswith("/png"):
		return ".png"
	if mt.endswith("/jpeg") or mt.endswith("/jpg"):
		return ".jpg"
	if mt.endswith("/webp"):
		return ".webp"
	return ".bin"


def _ensure_dir(path: str) -> None:
	os.makedirs(path, exist_ok=True)


def _safe_json_dump(obj: Any) -> str:
	return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


def _message_role_from_langchain(msg: Any) -> str:
	msg_type = getattr(msg, "type", None)
	if msg_type == "system":
		return "system"
	if msg_type in ("human", "user"):
		return "user"
	if msg_type in ("ai", "assistant"):
		return "assistant"
	return "user"


def normalize_messages(messages: Any) -> List[Dict[str, Any]]:
	if not messages:
		return []

	normalized: List[Dict[str, Any]] = []
	for msg in list(messages):
		if isinstance(msg, dict):
			role = msg.get("role", "user")
			normalized.append({"role": role, "content": msg.get("content", "")})
			continue

		role = _message_role_from_langchain(msg)
		content = getattr(msg, "content", "")
		normalized.append({"role": role, "content": content})

	return normalized


def _sanitize_content(
	exp_dir: str,
	content: Any,
	step_idx: Optional[int],
	call_idx: Optional[int],
) -> Any:
	if not isinstance(content, (list, tuple)):
		return content

	sanitized_parts: List[Dict[str, Any]] = []
	image_counter = 0

	for part in content:
		if not isinstance(part, dict):
			sanitized_parts.append({"type": "text", "text": str(part)})
			continue

		ptype = part.get("type")

		if ptype == "image_url":
			image_url = part.get("image_url") or {}
			url = image_url.get("url") if isinstance(image_url, dict) else None
			decoded = _decode_data_url(url or "") if isinstance(url, str) else None
			if decoded is None:
				sanitized_parts.append(part)
				continue

			media_type, raw = decoded
			sha256 = _sha256_bytes(raw)
			ext = _ext_for_media_type(media_type)

			images_dir = _images_dir(exp_dir)
			_ensure_dir(images_dir)

			s = step_idx if step_idx is not None else -1
			c = call_idx if call_idx is not None else -1
			filename = f"step_{s}_call_{c}_{image_counter}{ext}"
			image_counter += 1

			out_path = os.path.join(images_dir, filename)
			try:
				with open(out_path, "wb") as f:
					f.write(raw)
			except Exception:
				sanitized_parts.append(part)
				continue

			sanitized_parts.append(
				{
					"type": "image_ref",
					"ref": {
						"path": f"images/{filename}",
						"sha256": sha256,
						"media_type": media_type,
					},
				}
			)
			continue

		sanitized_parts.append(part)

	return sanitized_parts


def sanitize_messages(exp_dir: str, messages: List[Dict[str, Any]], *, call_idx: int) -> List[Dict[str, Any]]:
	step_idx = get_step_idx()

	sanitized: List[Dict[str, Any]] = []
	for msg in messages:
		role = msg.get("role", "user")
		content = msg.get("content", "")
		sanitized.append(
			{
				"role": role,
				"content": _sanitize_content(exp_dir, content, step_idx, call_idx),
			}
		)

	return sanitized


def append_event(
	*,
	provider: str,
	model: Optional[str],
	messages: Any,
	assistant_raw: Optional[str] = None,
	usage: Optional[Dict[str, Any]] = None,
	finish_reason: Optional[str] = None,
	request_id: Optional[str] = None,
	response_id: Optional[str] = None,
	latency_ms: Optional[float] = None,
	error: Optional[Dict[str, Any]] = None,
) -> None:
	exp_dir = _get_exp_dir()
	if not exp_dir:
		return

	step_idx = get_step_idx()
	call_idx = next_call_idx()

	normalized = normalize_messages(messages)
	sanitized = sanitize_messages(exp_dir, normalized, call_idx=call_idx)

	event = {
		"event_id": uuid.uuid4().hex,
		"ts": _now_iso(),
		"step_idx": step_idx,
		"call_idx": call_idx,
		"provider": provider,
		"model": model,
		"request": {
			"messages": sanitized,
		},
		"response": {
			"assistant_raw": assistant_raw,
			"usage": usage,
			"finish_reason": finish_reason,
			"request_id": request_id,
			"response_id": response_id,
		},
		"timing": {
			"latency_ms": latency_ms,
		},
		"error": error,
	}

	tmp_path = _tmp_jsonl_path(exp_dir)
	try:
		with open(tmp_path, "a", encoding="utf-8") as f:
			f.write(_safe_json_dump(event))
			f.write("\n")
	except Exception:
		return


def finalize_conversation_history() -> Optional[str]:
	exp_dir = _get_exp_dir()
	if not exp_dir:
		return None

	tmp_glob = os.path.join(exp_dir, "conversation_history.*.jsonl.tmp")
	tmp_files = sorted(glob.glob(tmp_glob))
	if not tmp_files:
		return None

	events: List[Dict[str, Any]] = []
	seen_ids: set[str] = set()

	for path in tmp_files:
		try:
			with open(path, "r", encoding="utf-8") as f:
				for line in f:
					line = line.strip()
					if not line:
						continue
					try:
						evt = json.loads(line)
					except Exception:
						continue
					event_id = evt.get("event_id")
					if event_id and event_id in seen_ids:
						continue
					if event_id:
						seen_ids.add(event_id)
					events.append(evt)
		except Exception:
			continue

	def _sort_key(evt: Dict[str, Any]) -> Tuple[int, int, str]:
		s = evt.get("step_idx")
		c = evt.get("call_idx")
		ts = evt.get("ts") or ""
		return (int(s) if s is not None else -1, int(c) if c is not None else -1, str(ts))

	events.sort(key=_sort_key)

	meta = {
		"run_id": os.environ.get("WEBARENA_RUN_ID"),
		"task_name": os.environ.get("WEBARENA_TASK_NAME"),
		"model_name": os.environ.get("WEBARENA_MODEL_NAME"),
		"created_at": _now_iso(),
		"exp_dir_before_rename": exp_dir,
	}

	final_obj = {
		"schema_version": _SCHEMA_VERSION,
		"meta": meta,
		"events": events,
	}

	final_path = _final_json_path(exp_dir)
	tmp_final = final_path + ".tmp"
	try:
		with open(tmp_final, "w", encoding="utf-8") as f:
			json.dump(final_obj, f, ensure_ascii=False, indent=2)
		os.replace(tmp_final, final_path)
	except Exception:
		return None

	return final_path
