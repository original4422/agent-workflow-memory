from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from browsergym.core.action.highlevel import HighLevelActionSet
from browsergym.experiments import Agent, AbstractAgentArgs
from browsergym.utils.obs import flatten_axtree_to_str, flatten_dom_to_str, prune_html

import openai

from ..cloudgpt_aoai.cloudgpt_aoai import get_openai_client

from ..retrieval.embedder import Embedder
from ..retrieval.index import ExperienceIndex, build_or_load_index
from ..retrieval.retrieve import RetrievedExperience, retrieve_top_k
from ..trace.types import RetrievalTrace, StepTrace
from ..trace.writer import TraceWriter
from experience_demo.trace.conversation_history import ConversationHistoryWriter
from .actions import extract_action_text, validate_action
from .prompting import build_system_prompt, build_user_prompt


def _clip(text: str, max_chars: int) -> str:
    """Clip long text by keeping head and tail segments."""
    if text is None:
        return ""
    text = str(text)
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return head + "\n...<clipped>...\n" + tail


class LLMClient:
    @staticmethod
    def make_llm_client(model_provider: str) -> openai.AzureOpenAI:
        """Create an LLM client for the requested provider."""
        provider = (model_provider or "").strip().lower()
        if provider in ("cloudgpt", "azure"):
            return LLMClient._make_cloudgpt_client()
        raise ValueError(
            "Unsupported model_provider: "
            + repr(model_provider)
            + ". Supported: cloudgpt"
        )

    @staticmethod
    def _make_cloudgpt_client() -> openai.AzureOpenAI:
        """Create a CloudGPT (AOAI) client."""
        # Intentionally use ONLY the official CloudGPT AOAI helper.
        # Do not read environment variables or fall back to DefaultAzureCredential here.
        return get_openai_client()


class ExperienceDemoAgent(Agent):
    """A minimal BrowserGym agent that can inject retrieved 'experiences' into the system prompt."""

    action_set = HighLevelActionSet(
        subsets=["chat", "bid", "nav", "tab", "infeas"],
        strict=False,
        multiaction=True,
    )

    def __init__(
        self,
        model_provider: str,
        model_name: str,
        use_experience: bool,
        top_k: int,
        experiences_path: Path,
        embedding_model_name: str,
        obs_mode: str,
        max_retry: int,
        max_obs_chars: int,
        max_history_turns: int,
        log_dir: Optional[Path] = None,
    ) -> None:
        super().__init__()

        self.model_provider = model_provider
        self.model_name = model_name
        self.use_experience = use_experience
        self.top_k = top_k
        self.experiences_path = experiences_path
        self.embedding_model_name = embedding_model_name
        self.obs_mode = obs_mode
        self.max_retry = max_retry
        self.max_obs_chars = max_obs_chars
        self.max_history_turns = max_history_turns

        self._step_idx = 0
        self._system_prompt: Optional[str] = None
        self._retrieved: List[RetrievedExperience] = []
        self._chat_history: List[Dict[str, str]] = []

        self._embedder = Embedder(model_name=self.embedding_model_name)
        self._index: Optional[ExperienceIndex] = None

        self._client = LLMClient.make_llm_client(self.model_provider)

        self._trace: Optional[TraceWriter] = TraceWriter(log_dir) if log_dir else None
        self._conv: Optional[ConversationHistoryWriter] = ConversationHistoryWriter(Path(log_dir)) if log_dir else None

    def close(self) -> None:
        """Close resources held by the agent (e.g., trace writer)."""
        if self._trace:
            self._trace.close()
            self._trace = None

    def obs_preprocessor(self, obs: dict) -> dict:
        """Convert raw observations into prompt-ready fields."""
        goal = obs.get("goal", "")
        url = obs.get("url", "")

        out: Dict[str, Any] = {
            "goal": goal,
            "url": url,
            # keep screenshot so ExpArgs can persist it every step
            "screenshot": obs.get("screenshot", None),
            "screenshot_som": obs.get("screenshot_som", None),
        }

        if self.obs_mode in ("axtree", "both") and "axtree_object" in obs:
            out["axtree_txt"] = _clip(flatten_axtree_to_str(obs["axtree_object"]), self.max_obs_chars)
        if self.obs_mode in ("html", "both") and "dom_object" in obs:
            dom_txt = flatten_dom_to_str(obs["dom_object"])
            out["dom_txt"] = _clip(prune_html(dom_txt), self.max_obs_chars)

        # pass through task_info if present
        if "task_info" in obs:
            out["task_info"] = obs["task_info"]
        return out

    def _ensure_index(self) -> ExperienceIndex:
        """Build or load the experience embedding index."""
        if self._index is None:
            self._index = build_or_load_index(self.experiences_path, self._embedder)
        return self._index

    def _ensure_retrieval(self, goal: str) -> List[RetrievedExperience]:
        """Retrieve and cache experiences for the current goal."""
        if not self.use_experience:
            return []
        if self._retrieved:
            return self._retrieved

        index = self._ensure_index()
        self._retrieved = retrieve_top_k(
            query=goal,
            index=index,
            embedder=self._embedder,
            top_k=self.top_k,
            site="shopping_admin",
        )

        if self._trace:
            self._trace.log_retrieval(
                RetrievalTrace(
                    query=goal,
                    top_k=self.top_k,
                    model_name=index.model_name,
                    results=[
                        {
                            "id": r.experience.id,
                            "score": r.score,
                            "site": r.experience.site,
                            "tags": r.experience.tags,
                            "summary": r.experience.summary,
                            "content": r.experience.content,
                        }
                        for r in self._retrieved
                    ],
                )
            )

        return self._retrieved

    def _build_system_prompt(self, goal: str) -> str:
        """Build the system prompt, optionally injecting retrieved experiences."""
        action_space_hint = _clip(
            self.action_set.describe(with_long_description=False, with_examples=True),
            6000,
        )
        retrieved = self._ensure_retrieval(goal)
        retrieved_contents = [r.experience.content for r in retrieved]
        return build_system_prompt(goal=goal, action_space_hint=action_space_hint, retrieved_experiences_content=retrieved_contents)

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        """Call the chat completion API with history."""
        messages = [{"role": "system", "content": system_prompt}]
        if self._chat_history:
            messages.extend(self._chat_history)
        messages.append({"role": "user", "content": user_prompt})

        resp = self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.2,
        )
        assistant = (resp.choices[0].message.content or "").strip()

        # Record every request (including retries) as a (user, assistant) pair.
        if self._conv is not None:
            self._conv.append_pair(user=user_prompt, assistant=assistant)

        return assistant

    def _push_history(self, user: str, assistant: str) -> None:
        """Append one user/assistant turn to the rolling chat history."""
        self._chat_history.append({"role": "user", "content": user})
        self._chat_history.append({"role": "assistant", "content": assistant})
        # keep only last N turns
        max_msgs = max(0, self.max_history_turns) * 2
        if max_msgs and len(self._chat_history) > max_msgs:
            self._chat_history = self._chat_history[-max_msgs:]

    def get_action(self, obs: dict) -> Tuple[str, dict]:
        """Compute the next action given the current observation.

        Args:
            obs: Preprocessed observation dict (see `obs_preprocessor`).

        Returns:
            A tuple `(action_text, agent_info)` where `action_text` is a single
            action call string.
        """
        goal = obs.get("goal", "")
        url = obs.get("url", "")

        if self._system_prompt is None:
            self._system_prompt = self._build_system_prompt(goal)

        obs_parts: List[str] = []
        if self.obs_mode in ("axtree", "both"):
            obs_parts.append(obs.get("axtree_txt", ""))
        if self.obs_mode in ("html", "both"):
            obs_parts.append(obs.get("dom_txt", ""))
        obs_text = "\n\n".join([p for p in obs_parts if p])
        if not obs_text:
            obs_text = str({k: v for k, v in obs.items() if k not in ("screenshot", "screenshot_som")})

        prompt_bundle = build_user_prompt(step=self._step_idx, url=url, obs_text=obs_text, max_obs_chars=self.max_obs_chars)

        raw = ""
        action_text = ""
        action_valid = False
        error: Optional[str] = None

        for attempt in range(max(1, self.max_retry)):
            raw = self._chat(system_prompt=self._system_prompt, user_prompt=prompt_bundle.user)
            candidate = extract_action_text(raw)
            action_valid, error = validate_action(self.action_set, candidate)
            if action_valid:
                action_text = candidate
                break

            # Ask for a corrected action next retry (keep it minimal; no chain-of-thought)
            correction = (
                "Your previous output was not a valid action. "
                "Output ONLY one valid action function call from the action space. "
                f"Parsing error: {error}"
            )
            self._push_history(prompt_bundle.user, raw)
            prompt_bundle = dataclasses.replace(
                prompt_bundle,
                user=prompt_bundle.user + "\n\n# Correction\n" + correction,
            )

        if not action_text:
            action_text = "noop(500)"
            action_valid, error = validate_action(self.action_set, action_text)

        self._push_history(prompt_bundle.user, raw)

        agent_info: Dict[str, Any] = {
            "llm_output": raw,
            "action_valid": action_valid,
            "error": error,
            "use_experience": self.use_experience,
            "retrieved": [
                {
                    "id": r.experience.id,
                    "score": r.score,
                }
                for r in self._retrieved
            ],
            "chat_messages": [m["content"] for m in ([{"role": "system", "content": self._system_prompt}] + self._chat_history)],
        }

        if self._trace:
            self._trace.log_step(
                StepTrace(
                    step=self._step_idx,
                    url=url,
                    obs_excerpt=prompt_bundle.obs_excerpt,
                    prompt_user=prompt_bundle.user,
                    prompt_system=self._system_prompt,
                    llm_output=raw,
                    action_text=action_text,
                    action_valid=action_valid,
                    error=error,
                    screenshot_path=None,
                )
            )

        self._step_idx += 1
        return action_text, agent_info


@dataclasses.dataclass
class ExperienceDemoAgentArgs(AbstractAgentArgs):
    """Arguments for constructing an `ExperienceDemoAgent`."""
    model_provider: str = "cloudgpt"
    model_name: str = "gpt-4.1-20250414"
    use_experience: bool = False
    top_k: int = 3
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    experiences_path: str = ""
    obs_mode: str = "axtree"  # axtree|html|both
    max_retry: int = 5
    max_obs_chars: int = 8000
    max_history_turns: int = 4
    log_dir: str = ""

    def make_agent(self) -> Agent:
        """Instantiate the agent."""
        experiences_path = Path(self.experiences_path)
        log_dir = Path(self.log_dir) if self.log_dir else None
        return ExperienceDemoAgent(
            model_provider=self.model_provider,
            model_name=self.model_name,
            use_experience=self.use_experience,
            top_k=self.top_k,
            experiences_path=experiences_path,
            embedding_model_name=self.embedding_model_name,
            obs_mode=self.obs_mode,
            max_retry=self.max_retry,
            max_obs_chars=self.max_obs_chars,
            max_history_turns=self.max_history_turns,
            log_dir=log_dir,
        )
