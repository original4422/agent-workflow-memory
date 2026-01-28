from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


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


@dataclass(frozen=True)
class PromptBundle:
    system: str
    user: str
    obs_excerpt: str


def build_system_prompt(
    goal: str,
    action_space_hint: str,
    retrieved_experiences_content: Optional[List[str]] = None,
    think_prompt: bool = True,
) -> str:
    """Build the system prompt for one episode."""
    exp_block = ""
    if retrieved_experiences_content:
        joined = "\n\n".join(
            [f"## Experience {i+1}\n{c.strip()}" for i, c in enumerate(retrieved_experiences_content)]
        )
        exp_block = f"\n\n# Retrieved Experiences (use as rules/shortcuts)\n{joined}\n"

    if think_prompt:
        return (
            "# Instructions\n"
            "You are controlling a web browser via a restricted high-level action language.\n"
            "Your output will be parsed and executed by a program.\n\n"
            "## Output format (MANDATORY)\n"
            "- Provide a short rationale (2-5 lines) inside <think>...</think>.\n"
            "- Provide the action on the LAST LINE, wrapped as: <action>YOUR_ACTION_HERE</action>.\n"
            "- Do NOT use markdown.\n\n"
            "## Action rules\n"
            "- Output a single best next action per step.\n"
            "- To finish and submit the final answer, use send_msg_to_user(<answer>).\n\n"
            f"# Goal\n{goal}\n\n"
            f"# Action Space\n{action_space_hint}\n"
            + exp_block
        )
    else:
        return (
            "# Instructions\n"
            "You are controlling a web browser via a restricted high-level action language.\n"
            "Your output will be parsed and executed by a program.\n\n"
            "## Output format (MANDATORY)\n"
            "- Provide the action on the LAST LINE, wrapped as: <action>YOUR_ACTION_HERE</action>.\n"
            "- Do NOT add explanations, markdown, or extra text.\n\n"
            "## Action rules\n"
            "- Output a single best next action per step.\n"
            "- To finish and submit the final answer, use send_msg_to_user(<answer>).\n\n"
            f"# Goal\n{goal}\n\n"
            f"# Action Space\n{action_space_hint}\n"
            + exp_block
        )


def build_user_prompt(
    step: int,
    url: str,
    obs_text: str,
    max_obs_chars: int = 8000,
) -> PromptBundle:
    """Build the user prompt bundle for one step."""
    obs_excerpt = _clip(obs_text, max_obs_chars)
    user = (
        f"# Step\n{step}\n\n"
        f"# Current URL\n{url}\n\n"
        "# Observation (Accessibility Tree / DOM excerpt)\n"
        f"{obs_excerpt}\n\n"
        "# Output\n"
        "Return the single best next action as a Python-like function call."
    )
    return PromptBundle(system="", user=user, obs_excerpt=obs_excerpt)
