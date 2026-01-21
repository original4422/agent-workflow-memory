from __future__ import annotations

import re
from typing import Optional, Tuple

from browsergym.core.action.base import AbstractActionSet


_CODE_FENCE_RE = re.compile(r"```(?:python)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


def extract_action_text(raw: str) -> str:
	if raw is None:
		return ""
	raw = str(raw).strip()
	if not raw:
		return ""

	m = _CODE_FENCE_RE.search(raw)
	if m:
		raw = m.group(1).strip()

	# If the model returned multiple lines, prefer the first non-empty line that looks like a call.
	for line in raw.splitlines():
		s = line.strip()
		if not s:
			continue
		if "(" in s and ")" in s:
			return s

	return raw.splitlines()[0].strip() if raw.splitlines() else ""


def validate_action(action_set: AbstractActionSet, action_text: str) -> Tuple[bool, Optional[str]]:
	if not action_text:
		return False, "empty action"
	try:
		_ = action_set.to_python_code(action_text)
		return True, None
	except Exception as e:
		return False, str(e)
