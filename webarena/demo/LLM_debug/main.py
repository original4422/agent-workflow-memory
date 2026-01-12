import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List


def _ensure_webarena_on_syspath() -> None:
    here = Path(__file__).resolve()
    # .../webarena/demo/LLM_debug/main.py -> parents[2] == .../webarena
    webarena_dir = here.parents[2]
    sys.path.insert(0, str(webarena_dir))


_ensure_webarena_on_syspath()

from llm_client import LLMClient, build_config  # noqa: E402


def load_system_prompt(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def load_user_prompts(path: Path) -> List[str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    prompts = data.get("user_prompt", [])
    if not isinstance(prompts, list):
        raise ValueError("user_prompt must be a list")
    return [str(x) for x in prompts]


def save_messages(messages: List[Dict[str, str]], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "conversation_history.json"
    # Requirement: conversation_history.json is messages
    out_path.write_text(json.dumps(messages, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--api-type",
        type=str,
        required=True,
        choices=["azure", "openai", "kimi", "glm"],
        help="LLM API type: azure or OpenAI-compatible (openai/kimi/glm)",
    )
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Model name to use (e.g., gpt-4o-20241120-2, gpt-4.1-20250414, gpt-5-20250807)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for OpenAI-compatible providers (required when --api-type != azure)",
    )
    parser.add_argument(
        "--base-url",
        type=str,
        default=None,
        help="Base URL for OpenAI-compatible providers (recommended for kimi/glm)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature (default: 0.2)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Max tokens for the response (default: 1024)",
    )
    parser.add_argument(
        "--prompt-dir",
        type=str,
        default=str(Path(__file__).parent / "prompt"),
        help="Directory containing system_prompt.txt and user/user_prompt.json",
    )
    parser.add_argument(
        "--result-dir",
        type=str,
        default=str(Path(__file__).parent / "result"),
        help="Directory to store timestamped results",
    )
    args = parser.parse_args()

    if args.api_type != "azure" and not args.api_key:
        parser.error("--api-key is required when --api-type != azure")

    prompt_dir = Path(args.prompt_dir)
    system_path = prompt_dir / "system_prompt.txt"
    user_path = prompt_dir / "user" / "user_prompt.json"

    system_prompt = load_system_prompt(system_path)
    user_prompts = load_user_prompts(user_path)

    cfg = build_config(
        api_type=args.api_type,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        api_key=args.api_key,
        base_url=args.base_url,
    )
    client = LLMClient(cfg)

    messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]

    for idx, user_content in enumerate(user_prompts, start=1):
        messages.append({"role": "user", "content": user_content})
        assistant_content = client.chat(messages)
        messages.append({"role": "assistant", "content": assistant_content})
        print(f"[{idx}/{len(user_prompts)}] assistant: {assistant_content[:200]}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.result_dir) / ts
    out_path = save_messages(messages, out_dir)
    print(f"[INFO] saved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
