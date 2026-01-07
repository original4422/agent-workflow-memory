import json
import os
import tempfile
import atexit
import sys
import subprocess
from pathlib import Path
from webarena.browser_env import ScriptBrowserEnv, create_id_based_action

# WebArena's installed ScriptBrowserEnv expects the config file to be a single dict.
# Many generators output a list of tasks; this helper selects one and adapts it.
def _prepare_single_task_config(config_path: str) -> str:
    config_file = Path(config_path)
    with config_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Select one task if a list is provided.
    task = None
    if isinstance(data, list):
        task_id_env = os.environ.get("TASK_ID")
        task_index_env = os.environ.get("TASK_INDEX")

        if task_id_env is not None:
            wanted_id = int(task_id_env)
            for item in data:
                if isinstance(item, dict) and item.get("task_id") == wanted_id:
                    task = item
                    break
            if task is None:
                raise ValueError(f"TASK_ID={wanted_id} not found in {config_path}")
        else:
            index = int(task_index_env) if task_index_env is not None else 0
            try:
                task = data[index]
            except Exception as e:
                raise ValueError(f"Invalid TASK_INDEX={index} for {config_path}") from e
    elif isinstance(data, dict):
        task = data
    else:
        raise TypeError(f"Unsupported config JSON type: {type(data).__name__}")

    if not isinstance(task, dict):
        raise TypeError(f"Selected task must be a dict, got: {type(task).__name__}")

    webarena_root = Path(__file__).resolve().parents[2]  # .../webarena

    # Resolve/override storage_state.
    # - You can override via env var STORAGE_STATE=/abs/path/to/state.json
    # - If missing, we drop it so Playwright starts with a fresh context.
    storage_state_override = os.environ.get("STORAGE_STATE")
    if storage_state_override:
        override_path = Path(storage_state_override).expanduser().resolve()
        if not override_path.exists():
            raise FileNotFoundError(f"STORAGE_STATE does not exist: {override_path}")
        task["storage_state"] = str(override_path)
    else:
        storage_state = task.get("storage_state")
        if isinstance(storage_state, str) and storage_state:
            storage_path = Path(storage_state)
            if not storage_path.is_absolute():
                # Try a few common bases.
                rel = Path(str(storage_path).lstrip("./"))
                base_candidates = [
                    config_file.parent,
                    Path(__file__).resolve().parent,
                    webarena_root,
                    Path(__file__).resolve().parents[3],  # repo root
                ]
                resolved = None
                for base in base_candidates:
                    candidate = (base / rel).resolve()
                    if candidate.exists():
                        resolved = candidate
                        break

                if resolved is None:
                    # WebArena provides an auto-login script to generate these cookies.
                    # The task generator commonly writes relative paths like ./.auth/shopping_admin_state.json,
                    # which are expected to live under the WebArena project root.
                    require_login = bool(task.get("require_login", False))
                    auth_folder = (webarena_root / ".auth").resolve()
                    target_state = (webarena_root / rel).resolve()

                    # If this looks like a standard .auth/*_state.json path, try to generate it.
                    auto_login_enabled = os.environ.get("AUTO_LOGIN") in {"1", "true", "True"}
                    if require_login and (".auth" in str(rel).split(os.sep)):
                        auth_folder.mkdir(parents=True, exist_ok=True)

                        # env_config.py expects un-prefixed names, while this repo's README uses WA_*.
                        env = dict(os.environ)
                        mapping = {
                            "REDDIT": "WA_REDDIT",
                            "SHOPPING": "WA_SHOPPING",
                            "SHOPPING_ADMIN": "WA_SHOPPING_ADMIN",
                            "GITLAB": "WA_GITLAB",
                            "WIKIPEDIA": "WA_WIKIPEDIA",
                            "MAP": "WA_MAP",
                            "HOMEPAGE": "WA_HOMEPAGE",
                        }
                        for k, wa_k in mapping.items():
                            if not env.get(k) and env.get(wa_k):
                                env[k] = env[wa_k]

                        missing = [k for k in mapping.keys() if not env.get(k)]
                        if missing:
                            raise FileNotFoundError(
                                "storage_state not found and auto-login requires URL env vars. "
                                f"Missing: {missing}. Set them (or set the WA_* equivalents), then rerun. "
                                "Example: export SHOPPING_ADMIN=... (or WA_SHOPPING_ADMIN=...)"
                            )

                        if auto_login_enabled:
                            site = rel.name.replace("_state.json", "")
                            cmd = [
                                sys.executable,
                                "-m",
                                "webarena.browser_env.auto_login",
                                "--site_list",
                                site,
                                "--auth_folder",
                                str(auth_folder),
                            ]
                            subprocess.run(cmd, check=True, env=env)

                            if target_state.exists():
                                task["storage_state"] = str(target_state)
                            else:
                                raise FileNotFoundError(
                                    "Auto-login completed but storage_state still missing: "
                                    f"{target_state}. Check the generated files under {auth_folder}"
                                )
                        else:
                            raise FileNotFoundError(
                                "storage_state file not found for a login-required task. "
                                f"Expected something like: {target_state}. "
                                "To generate it using WebArena's built-in script, run with AUTO_LOGIN=1."
                            )
                    else:
                        print(
                            "[WARN] storage_state file not found; starting with a fresh browser context. "
                            f"storage_state={storage_state} config={config_path}"
                        )
                        task.pop("storage_state", None)
                else:
                    task["storage_state"] = str(resolved)

    # Write to a temp file because ScriptBrowserEnv takes a file path.
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    tmp_path = tmp.name
    json.dump(task, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    atexit.register(lambda p=tmp_path: os.path.exists(p) and os.remove(p))
    return tmp_path

# 1. 准备你的配置文件路径（强烈建议使用绝对路径，避免相对路径解析错误）
task_config_path = os.path.join(os.path.dirname(__file__), "../task_generate/generated_task/tasks_20260105_150433.json")
task_config_path = os.path.abspath(task_config_path)

if not os.path.exists(task_config_path):
    raise FileNotFoundError(
        f"Task config file not found: {task_config_path}. "
        "Create it or update task_config_path to point to your JSON config."
    )

# 2. 初始化环境
# 这里的参数根据你的实验需求调整
env = ScriptBrowserEnv(
    headless=False,  # 设置为 True 则不显示浏览器窗口
    observation_type="accessibility_tree",
    current_viewport_only=True,
    viewport_size={"width": 1280, "height": 720},
)

# 3. 加载自定义任务
# 关键点：env.reset 接收一个 options 字典，其中 "config_file" 可以是任意路径
single_task_config_path = _prepare_single_task_config(task_config_path)
print(f"Loading task from: {task_config_path}")
print(f"Using single-task config: {single_task_config_path}")
obs, info = env.reset(options={"config_file": single_task_config_path})

# 4. 验证任务是否加载成功
with open(single_task_config_path, "r", encoding="utf-8") as f:
    selected_task = json.load(f)

intent = None
if isinstance(info, dict):
    intent = info.get("intent")
if not intent and isinstance(selected_task, dict):
    intent = selected_task.get("intent")

print(f"当前任务 Intent: {intent}")

if isinstance(obs, dict) and "text" in obs and isinstance(obs["text"], str):
    print(f"当前页面观测(text): {obs['text'][:100]}...")
elif isinstance(obs, dict):
    print(f"当前页面观测 keys: {list(obs.keys())}")
else:
    print(f"当前页面观测类型: {type(obs).__name__}")

# --- 下面是你的 Agent 循环逻辑 ---
try:
    # 示例：执行一个空动作或简单动作
    # 在实际代码中，这里是你的 Agent 模型 loop
    # action = my_agent.get_action(obs) 
    
    # 演示：随机生成一个 action
    action = create_id_based_action("click [10]") 
    
    obs, reward, terminated, truncated, info = env.step(action)
    print("Action executed.")
    
finally:
    env.close()