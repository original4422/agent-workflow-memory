from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List


class ConversationHistoryWriter:
    """Persist full conversation history under <log_dir>/conversation_history/.

        File format: JSON array of messages:
            [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."},
                {"role": "assistant", "content": "..."},
                ...
            ]

    Only message content is stored (no tokens/usage/ids).
    """

    def __init__(self, log_dir: Path) -> None:
        self._log_dir = Path(log_dir)
        self._dir = self._log_dir / "conversation_history"
        self._path = self._dir / "conversation_history.json"
        self._dir.mkdir(parents=True, exist_ok=True)
        # Each run starts a brand-new conversation history.
        self._messages: List[Dict[str, str]] = []

    def _atomic_write(self) -> None:
        tmp_path = self._path.with_suffix(self._path.suffix + ".tmp")
        data = json.dumps(self._messages, ensure_ascii=False, indent=2)
        tmp_path.write_text(data + "\n", encoding="utf-8")
        os.replace(tmp_path, self._path)

    def ensure_system(self, system: str) -> None:
        if not self._messages:
            self._messages.append({"role": "system", "content": str(system)})
            self._atomic_write()
            return

        first = self._messages[0]
        if isinstance(first, dict) and first.get("role") == "system":
            return

        # If there are already messages but no system at the top, prepend it.
        self._messages.insert(0, {"role": "system", "content": str(system)})
        self._atomic_write()

    def append_pair(self, *, user: str, assistant: str) -> None:
        self._messages.append({"role": "user", "content": str(user)})
        self._messages.append({"role": "assistant", "content": str(assistant)})
        self._atomic_write()
