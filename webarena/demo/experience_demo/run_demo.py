from __future__ import annotations

import argparse
import datetime
import importlib.resources as importlib_resources
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from browsergym.experiments import EnvArgs, ExpArgs


def _ensure_importable() -> None:
	# When executed as a script, ensure the parent folder is on sys.path
	here = Path(__file__).resolve().parent
	parent = here.parent
	if str(parent) not in sys.path:
		sys.path.insert(0, str(parent))


_ensure_importable()

from experience_demo.agent.agent import ExperienceDemoAgentArgs  # noqa: E402


def str2bool(v):
	if isinstance(v, bool):
		return v
	if v.lower() in ("yes", "true", "t", "y", "1"):
		return True
	if v.lower() in ("no", "false", "f", "n", "0"):
		return False
	raise argparse.ArgumentTypeError("Boolean value expected.")


def parse_args() -> argparse.Namespace:
	p = argparse.ArgumentParser()
	p.add_argument("--task_name", type=str, default="webarena.1")
	p.add_argument("--task_config_path", type=str, default=str(Path(__file__).resolve().parents[2] / "config_files" / "test.raw.json"))
	p.add_argument("--model_name", type=str, default="cloudgpt/gpt-4.1-20250414")
	p.add_argument("--headless", type=str2bool, default=True)
	p.add_argument("--slow_mo", type=int, default=30)
	p.add_argument("--max_steps", type=int, default=30)
	p.add_argument("--obs_mode", type=str, default="axtree", choices=["axtree", "html", "both"])
	p.add_argument("--use_experience", type=str2bool, default=False)
	p.add_argument("--top_k", type=int, default=3)
	p.add_argument("--embedding_model", type=str, default="sentence-transformers/all-MiniLM-L6-v2")
	p.add_argument("--suite", type=str2bool, default=False, help="Run baseline + with-experience each n_runs")
	p.add_argument("--n_runs", type=int, default=1)
	return p.parse_args()


def _patch_task_config_text(config_text: str, task_name: str, storage_state_path: Path) -> str:
	raw = json.loads(config_text)
	if not isinstance(raw, list):
		raise ValueError("Task config must be a JSON list")

	if task_name.startswith("webarena."):
		task_id = int(task_name.split(".", 1)[1])
		raw = [r for r in raw if int(r.get("task_id", -1)) == task_id]

	for r in raw:
		if "storage_state" in r:
			r["storage_state"] = str(storage_state_path)
	return json.dumps(raw, ensure_ascii=False, indent=2)


def _install_webarena_task_config_monkeypatch(config_text: str) -> None:
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


def _model_tag(model_name: str) -> str:
	return model_name.replace("/", "_").replace(":", "_")


def _run_once(
	*,
	task_name: str,
	model_name: str,
	headless: bool,
	slow_mo: int,
	max_steps: int,
	obs_mode: str,
	use_experience: bool,
	top_k: int,
	embedding_model: str,
	exp_root: Path,
	experiences_path: Path,
	# storage_state_path: Path,
) -> Dict[str, Any]:
	env_args = EnvArgs(
		task_name=task_name,
		task_seed=None,
		max_steps=max_steps,
		headless=headless,
		viewport={"width": 1500, "height": 1280},
		slow_mo=slow_mo,
		# storage_state=str(storage_state_path),
		task_kwargs=None,
	)

	agent_args = ExperienceDemoAgentArgs(
		model_name=model_name,
		use_experience=use_experience,
		top_k=top_k,
		embedding_model_name=embedding_model,
		experiences_path=str(experiences_path),
		obs_mode=obs_mode,
		max_retry=5,
		max_obs_chars=8000,
		max_history_turns=4,
		run_dir="",  # filled after prepare
	)

	mode = "with_exp" if use_experience else "baseline"
	exp_args = ExpArgs(agent_args=agent_args, env_args=env_args)
	exp_args.exp_name = f"ExperienceDemo_{mode}_{_model_tag(model_name)}"
	exp_args.prepare(exp_root=exp_root)

	# now that exp_dir exists, route demo trace to a subfolder
	exp_args.agent_args.run_dir = str(Path(exp_args.exp_dir) / "experience_demo")

	exp_args.run()

	summary_path = Path(exp_args.exp_dir) / "summary_info.json"
	summary_info: Dict[str, Any] = {}
	if summary_path.exists():
		summary_info = json.loads(summary_path.read_text(encoding="utf-8"))

	success = False
	try:
		success = bool(summary_info.get("terminated")) and float(summary_info.get("cum_reward", 0.0)) > 0.0
	except Exception:
		success = False

	return {
		"exp_dir": str(exp_args.exp_dir),
		"mode": mode,
		"success": success,
		"summary_info": summary_info,
	}


def main() -> None:
	args = parse_args()

	here = Path(__file__).resolve().parent
	experiences_path = here / "experience" / "experiences.jsonl"
	if not experiences_path.exists():
		raise FileNotFoundError(f"experiences.jsonl not found: {experiences_path}")

	# storage_state_path = here / ".auth" / "shopping_admin_state.json"
	# if not storage_state_path.exists():
	# 	raise FileNotFoundError(
	# 		"Missing storage_state. Create it at: " + str(storage_state_path)
	# 	)

	task_config_path = Path(args.task_config_path).resolve()
	if not task_config_path.exists():
		raise FileNotFoundError(f"Task config not found: {task_config_path}")

	if args.task_name.startswith("webarena."):
		config_text = task_config_path.read_text(encoding="utf-8")
		# patched = _patch_task_config_text(config_text, args.task_name, storage_state_path)
		_install_webarena_task_config_monkeypatch(config_text)

	results_root = here / "results"
	results_root.mkdir(parents=True, exist_ok=True)

	suite_dir: Path
	if args.suite:
		stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		suite_dir = results_root / f"{stamp}_suite_{args.task_name}_{_model_tag(args.model_name)}"
		suite_dir.mkdir(parents=True, exist_ok=True)
	else:
		suite_dir = results_root

	records: List[Dict[str, Any]] = []

	if args.suite:
		for mode_use_exp in (False, True):
			for _ in range(max(1, args.n_runs)):
				records.append(
					_run_once(
						task_name=args.task_name,
						model_name=args.model_name,
						headless=args.headless,
						slow_mo=args.slow_mo,
						max_steps=args.max_steps,
						obs_mode=args.obs_mode,
						use_experience=mode_use_exp,
						top_k=args.top_k,
						embedding_model=args.embedding_model,
						exp_root=suite_dir,
						experiences_path=experiences_path,
						# storage_state_path=storage_state_path,
					)
				)
	else:
		records.append(
			_run_once(
				task_name=args.task_name,
				model_name=args.model_name,
				headless=args.headless,
				slow_mo=args.slow_mo,
				max_steps=args.max_steps,
				obs_mode=args.obs_mode,
				use_experience=args.use_experience,
				top_k=args.top_k,
				embedding_model=args.embedding_model,
				exp_root=suite_dir,
				experiences_path=experiences_path,
				# storage_state_path=storage_state_path,
			)
		)

	report = {
		"task_name": args.task_name,
		"model_name": args.model_name,
		"obs_mode": args.obs_mode,
		"top_k": args.top_k,
		"suite": args.suite,
		"n_runs": args.n_runs,
		"records": records,
		"success_rate": {
			"baseline": float(
				sum(1 for r in records if r["mode"] == "baseline" and r["success"]) / max(1, sum(1 for r in records if r["mode"] == "baseline"))
			),
			"with_exp": float(
				sum(1 for r in records if r["mode"] == "with_exp" and r["success"]) / max(1, sum(1 for r in records if r["mode"] == "with_exp"))
			),
		},
	}

	out_json = suite_dir / "report.json"
	out_md = suite_dir / "report.md"
	out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

	md_lines = [
		f"# Experience Demo Report",
		f"",
		f"- task_name: {args.task_name}",
		f"- model_name: {args.model_name}",
		f"- obs_mode: {args.obs_mode}",
		f"- top_k: {args.top_k}",
		f"- baseline success rate: {report['success_rate']['baseline']:.2f}",
		f"- with-experience success rate: {report['success_rate']['with_exp']:.2f}",
		"",
		"## Runs",
	]
	for r in records:
		md_lines.append(f"- {r['mode']} | success={r['success']} | exp_dir={r['exp_dir']}")
	out_md.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

	print(f"Wrote report: {out_md}")


if __name__ == "__main__":
	main()
