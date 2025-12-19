# WebArena 代理执行与接入说明

## 背景与代码归属
- 入口脚本位于 [webarena/run.py](webarena/run.py)，以及代理实现 [webarena/agents/legacy/agent.py](webarena/agents/legacy/agent.py) 与提示逻辑 [webarena/agents/legacy/dynamic_prompting.py](webarena/agents/legacy/dynamic_prompting.py) 都是 AWM 提供的示例代码（仓库内置，文件头均标注已弃用）。
- WebArena 官方仓库（https://github.com/web-arena-x/webarena）提供的是环境与任务数据；运行时依赖的环境接口由 `browsergym` 与 `browsergym-webarena` 包提供，而非本仓库自带。

## run.py 的执行流程
1. **解析参数**：获取模型名、任务名（如 `webarena.0`）、启动 URL、是否 headless、是否截图/AXTree/HTML、是否启用多步动作、最大步数、工作流记忆文件等。
2. **准备环境参数**：构造 `EnvArgs`（来自 `browsergym.experiments`），设置任务标识、浏览器视口、慢速模式、headless 与任务特定参数（`openended` 任务会附加 `start_url`，并启用 `wait_for_user_message`）。
3. **构造代理参数**：通过 `GenericAgentArgs`（继承 `AbstractAgentArgs`）封装聊天模型配置与 `Flags`。`Flags` 控制观测模态（HTML/AXTree/截图）、历史/思维链、动作空间（高层 BId/Coord/Nav 等），以及可选的 workflow 记忆文件。
4. **创建实验与运行**：
   - `exp_args = ExpArgs(env_args=..., agent_args=GenericAgentArgs(...))`
   - `exp_args.prepare(Path("./results"))` 创建实验目录、装配环境与代理。
   - `exp_args.run()` 进入 BrowserGym 统一循环：环境 `reset` 后在每步调用代理 `get_action`，执行返回的 BrowserGym 动作，记录轨迹、截图与文本观测。
5. **结果落盘**：运行结束后，将实验目录重命名到 `results/{task_name}/{timestamp}/`。

## 代理在 WebArena 中的执行细节
- **观测预处理**：`GenericAgent.obs_preprocessor` 在收到的原始观测中添加 `dom_txt`（DOM 文本）、`axtree_txt`（可选坐标）、`pruned_html`（裁剪后 HTML），便于提示压缩。
- **提示构建与模型调用**：`GenericAgent.get_action` 组装系统提示与主提示（由 `MainPrompt` 动态拼接当前观测、历史、动作空间说明、可选思考与记忆），必要时裁剪到 `max_prompt_tokens`。若 `Flags.use_screenshot` 为真且模型具备视觉能力，则附带截图。调用 `chat_llm` 解析模型输出为结构化动作。
- **动作与回退**：通过 `dynamic_prompting._get_action_space` 选择 BrowserGym 的 `AbstractActionSet`（如 HighLevel、Coord、Nav 组合）。解析失败会触发有限次数的重试；最终返回 `(action, info_dict)` 给 BrowserGym 驱动器。

## 谁提供了什么？
- **AWM（本仓库）**：
  - 入口脚本、默认代理、提示与动作空间包装（上文文件）。
  - Workflow 记忆（可在 Flags 中指定 `workflow_path` 导入额外系统提示）。
- **WebArena 官方**：
  - 任务定义、网站 Docker、环境配置脚本（参见官方仓库）。
  - Python 接口通过 `browsergym-webarena` 暴露为 BrowserGym 任务（如 `task_name="webarena.0"`）。
- **BrowserGym 框架**：
  - 统一的 `EnvArgs`、`ExpArgs`、`Agent`/`AbstractAgentArgs` 抽象，以及动作集合定义。

## 代理如何被传入 WebArena
- `ExpArgs` 构造时传入 `agent_args`（必须继承 `AbstractAgentArgs` 并实现 `make_agent`）。BrowserGym 在运行时调用 `make_agent()` 实例化代理。
- agent需继承 `browsergym.experiments.Agent`，并至少实现：
  - `obs_preprocessor(self, obs) -> dict`：可选，返回追加字段后的观测。
  - `get_action(self, obs) -> Tuple[action, info]`：必需，返回 BrowserGym 动作对象（来自某个 `AbstractActionSet`）及用于记录的附加信息。
- 动作集合通过代理内部持有的 `action_set` 决定，需使用 `browsergym.core.action` 下的集合（例如 `HighLevelActionSet`、`PythonActionSet`、坐标/导航组合等）。

## 自定义代理接入步骤示例
1. **定义代理参数包装**（继承 `AbstractAgentArgs`）：
   ```python
   from browsergym.experiments import Agent, AbstractAgentArgs
   from browsergym.core.action.highlevel import HighLevelActionSet

   class MyAgentArgs(AbstractAgentArgs):
       def make_agent(self):
           return MyAgent()
   ```
2. **实现代理**（继承 `Agent`）：
   ```python
   class MyAgent(Agent):
       def __init__(self):
           self.action_set = HighLevelActionSet()

       def obs_preprocessor(self, obs):
           return obs  # 或添加自定义字段

       def get_action(self, obs):
           # 构造并返回 BrowserGym 动作对象
           action = self.action_set.click(selector="button")
           return action, {"note": "example"}
   ```
3. **在入口脚本中注入**：
   ```python
   from browsergym.experiments import EnvArgs, ExpArgs
   env_args = EnvArgs(task_name="webarena.0", headless=True)
   exp_args = ExpArgs(env_args=env_args, agent_args=MyAgentArgs())
   exp_args.prepare(Path("./results"))
   exp_args.run()
   ```
4. **可选能力**：添加截图/HTML/AXTree 预处理、历史与思考链管理、工作流记忆提示等，方式可参考默认代理实现。

## 关键点速览
- run.py 是 AWM 的示例入口，负责把本仓库代理注入 BrowserGym，再由 BrowserGym 驱动 WebArena 任务。
- WebArena 环境本身由官方包 `browsergym-webarena` 提供；只需在任务名里选择对应 task id 即可。
- 接入自定义代理的核心接口是 BrowserGym 的 `Agent`/`AbstractAgentArgs`；实现 `get_action` 并返回 BrowserGym 动作即可完成与 WebArena 的对接。
