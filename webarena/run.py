"""
WARNING DEPRECATED WILL BE REMOVED SOON
"""

import os
import argparse
import importlib.resources as importlib_resources
from pathlib import Path

from browsergym.experiments import ExpArgs, EnvArgs

from agents.legacy.agent import GenericAgentArgs
from agents.legacy.dynamic_prompting import Flags
from agents.legacy.utils.chat_api import ChatModelArgs
import datetime


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


def parse_args():
    parser = argparse.ArgumentParser(description="Run experiment with hyperparameters.")
    parser.add_argument(
        "--model_name",
        type=str,
        default="kimi/kimi-k2-thinking",
        help="Model name for the chat model (e.g., openai/gpt-4o, glm/glm-4.5, or kimi/kimi-k2-thinking).",
    )
    parser.add_argument(
        "--task_name",
        dest="task_name",
        type=str,
        default="openended",
        help=(
            "Name of the Browsergym task to run (e.g., webarena.0). "
            "If 'openended', you need to specify a 'start_url'"
        ),
    )
    parser.add_argument(
        "--start_url",
        type=str,
        default="https://www.google.com",
        help="Starting URL (only for the openended task).",
    )
    parser.add_argument(
        "--slow_mo", type=int, default=30, help="Slow motion delay for the playwright actions."
    )
    parser.add_argument(
        "--headless",
        type=str2bool,
        default=False,
        help="Run the experiment in headless mode (hides the browser windows).",
    )
    parser.add_argument(
        "--demo_mode",
        type=str2bool,
        default=True,
        help="Add visual effects when the agents performs actions.",
    )
    parser.add_argument(
        "--use_html", type=str2bool, default=False, help="Use HTML in the agent's observation space."
    )
    parser.add_argument(
        "--use_ax_tree",
        type=str2bool,
        default=True,
        help="Use AX tree in the agent's observation space.",
    )
    parser.add_argument(
        "--use_screenshot",
        type=str2bool,
        default=True,
        help="Use screenshot in the agent's observation space.",
    )
    parser.add_argument(
        "--multi_actions", type=str2bool, default=True, help="Allow multi-actions in the agent."
    )
    parser.add_argument(
        "--action_space",
        type=str,
        default="bid",
        choices=["python", "bid", "coord", "bid+coord", "bid+nav", "coord+nav", "bid+coord+nav"],
        help="",
    )
    parser.add_argument(
        "--use_history",
        type=str2bool,
        default=True,
        help="Use history in the agent's observation space.",
    )
    parser.add_argument(
        "--use_thinking",
        type=str2bool,
        default=True,
        help="Use thinking in the agent (chain-of-thought prompting).",
    )
    parser.add_argument(
        "--max_steps",
        type=int,
        default=50,
        help="Maximum number of steps to take for each task.",
    )
    parser.add_argument(
        "--workflow_path",
        type=str,
        default=None,
        help="Path to the memory file to load for the agent.",
    )
    parser.add_argument(
        "--task_config_path",
        type=str,
        default=None,
        help=(
            "Optional path to a JSON file that will be used to override the site-packages "
            "resource webarena/test.raw.json via a runtime monkeypatch (importlib.resources)."
        ),
    )

    return parser.parse_args()


def main():
    print(
        """\
WARNING this demo agent will soon be moved elsewhere. Expect it to be removed at some point."""
    )

    args = parse_args()
    if (args.workflow_path is not None) and (not os.path.exists(args.workflow_path)):
        open(args.workflow_path, "w").close()

    # Optional: override WebArena task config without touching site-packages.
    # browsergym.webarena.task reads:
    #   import webarena
    #   importlib.resources.files(webarena).joinpath("test.raw.json").read_text()
    # So we monkeypatch importlib.resources.files for the webarena package only.
    use_monkeypatch = False
    if args.task_config_path and args.task_name.startswith("webarena."):
        use_monkeypatch = True
        task_config_abs = str(Path(args.task_config_path).resolve())
        if not os.path.exists(task_config_abs):
            raise FileNotFoundError(f"Task config not found: {task_config_abs}")

        config_text = Path(task_config_abs).read_text(encoding="utf-8")
        target_resource_name = "test.raw.json"

        _orig_files = importlib_resources.files

        class _OverriddenResource:
            def __init__(self, content: str, encoding: str = "utf-8"):
                self._content = content
                self._encoding = encoding

            def read_text(self, *args, **kwargs):
                return self._content

            def read_bytes(self, *args, **kwargs):
                return self._content.encode(self._encoding)

            def open(self, mode: str = "r", *args, **kwargs):
                import io

                if "b" in mode:
                    return io.BytesIO(self.read_bytes())
                return io.StringIO(self._content)

        class _FilesProxy:
            def __init__(self, inner, overridden_name: str, overridden_text: str):
                self._inner = inner
                self._overridden_name = overridden_name
                self._overridden_text = overridden_text

            def joinpath(self, name):
                if name == self._overridden_name:
                    return _OverriddenResource(self._overridden_text)
                return self._inner.joinpath(name)

            def __truediv__(self, name):
                return self.joinpath(name)

        def _files_override(pkg):
            if getattr(pkg, "__name__", None) == "webarena":
                return _FilesProxy(_orig_files(pkg), target_resource_name, config_text)
            return _orig_files(pkg)

        importlib_resources.files = _files_override

    task_kwargs = None
    if args.task_name == "openended":
        task_kwargs = {"start_url": args.start_url}

    env_args = EnvArgs(
        task_name=args.task_name,
        task_seed=None,
        max_steps=args.max_steps,
        headless=args.headless,
        viewport={"width": 1500, "height": 1280},
        slow_mo=args.slow_mo,
        task_kwargs=task_kwargs,
    )

    if args.task_name == "openended":
        env_args.wait_for_user_message = True

    exp_args = ExpArgs(
        env_args=env_args,
        agent_args=GenericAgentArgs(
            chat_model_args=ChatModelArgs(
                model_name=args.model_name,
                max_total_tokens=128_000,  # "Maximum total tokens for the chat model."
                max_input_tokens=126_000,  # "Maximum tokens for the input to the chat model."
                max_new_tokens=4096,  # "Maximum total tokens for the chat model."
            ),
            flags=Flags(
                use_html=args.use_html,
                use_ax_tree=args.use_ax_tree,
                use_thinking=args.use_thinking,  # "Enable the agent with a memory (scratchpad)."
                use_error_logs=True,  # "Prompt the agent with the error logs."
                use_memory=False,  # "Enables the agent with a memory (scratchpad)."
                use_history=args.use_history,
                use_diff=False,  # "Prompt the agent with the difference between the current and past observation."
                use_past_error_logs=True,  # "Prompt the agent with the past error logs."
                use_action_history=True,  # "Prompt the agent with the action history."
                multi_actions=args.multi_actions,
                use_abstract_example=True,  # "Prompt the agent with an abstract example."
                use_concrete_example=True,  # "Prompt the agent with a concrete example."
                use_screenshot=args.use_screenshot,
                enable_chat=True,
                demo_mode="default" if args.demo_mode else "off",
                workflow_path=args.workflow_path,
            ),
        ),
    )

    exp_args.prepare(Path("./results"))
    exp_args.run()

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if use_monkeypatch:
        result_dir = Path(f"results/custom.{args.task_name}/{timestamp}/")
    else:
        result_dir = Path(f"results/{args.task_name}/{timestamp}/")
    os.makedirs(result_dir, exist_ok=True)
    os.rename(exp_args.exp_dir, result_dir)


if __name__ == "__main__":
    main()
