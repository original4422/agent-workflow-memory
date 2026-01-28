from __future__ import annotations

import re
from typing import Optional, Tuple

from browsergym.core.action.base import AbstractActionSet


_ACTION_TAG_RE = re.compile(r"<action>(.*?)</action>", re.DOTALL | re.IGNORECASE)


def _extract_from_action_tag(raw: str) -> str:
    m = _ACTION_TAG_RE.search(raw)
    if not m:
        return ""
    content = (m.group(1) or "").strip()
    if not content:
        return ""
    # Support both inline (<action>click('1')</action>) and block forms.
    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if not lines:
        return ""
    return lines[-1]


def extract_action_text(raw: str) -> str:
    """Extract a single action call from raw model output."""
    if raw is None:
        return ""
    raw = str(raw).strip()
    if not raw:
        return ""

    # Highest priority: explicit <action>...</action> wrapper.
    tagged = _extract_from_action_tag(raw)
    if tagged:
        return tagged

    return ""


def validate_action(action_set: AbstractActionSet, action_text: str) -> Tuple[bool, Optional[str]]:
    """Validate that `action_text` can be parsed by the action set."""
    if not action_text:
        return False, "empty action"
    try:
        _ = action_set.to_python_code(action_text)
        return True, None
    except Exception as e:
        return False, str(e)
