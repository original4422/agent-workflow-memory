# ExpArgs.run() 深入解析与自定义 Agent 指南

下述内容基于当前仓库的运行逻辑，核心参考自浏览器交互循环实现：

- 实验主循环：myenv/webarena/lib/python3.10/site-packages/browsergym/experiments/loop.py（ExpArgs、StepInfo、Agent 接口等）
- 现有示例 Agent：webarena/agents/legacy/agent.py（GenericAgent 与 GenericAgentArgs）

## 1. 从 `exp_args.run()` 开始的执行流程

1. 预处理
   - `ExpArgs.prepare()` 会设置随机种子、生成实验目录、序列化参数。
   - `run()` 开始时配置日志输出到 `experiment.log`，记录包版本。
2. 构建 Agent
   - 调用 `agent_args.make_agent()` 生成具体 Agent 实例（需实现于用户代码）。
   - Agent 应包含 `action_set`（含 `to_python_code` 映射）与 `obs_preprocessor()`（可选）。
3. 构建环境
   - `env_args.make_env(...)` 创建 BrowserGym 环境，使用 Agent 的 `action_set.to_python_code` 作为动作映射。
   - 根据 `env_args` 配置视窗、slow_mo、录像、存储状态等。
4. 重置并进入循环
   - `StepInfo.from_reset()` 重置环境并预处理观测（默认会把 DOM/AXTree 转文本）。
   - while 循环直到终止：
     - `step_info.from_action(agent)`：调用 Agent 的 `get_action(obs)` 获取动作与 `agent_info`。
     - 若动作为 None，标记截断并退出循环。
     - `step_info.save_step_info(...)`：保存观测、截图（可选）、统计信息。
     - 将思考与动作记录发送到 `env.unwrapped.chat` 便于日志/回放。
     - 创建下一步 `StepInfo`，调用 `from_step(env, action, obs_preprocessor)` 执行动作并获得下一观测、奖励、终止标记。
5. 结束与汇总
   - finally 中再次保存当前 step 信息。
   - 若循环未以终止/截断结束，会报“Early termination??”并写入错误。
   - `save_summary_info` 生成 `summary_info.json`：累计奖励、统计、终止/截断标记及错误堆栈。
   - 关闭环境，移除日志 handler。

终止条件：
- 环境返回 `terminated` 或 `truncated`。
- Agent 返回 None 动作（视为截断）。
- 未正常结束时触发 Early termination 错误并写入 summary。

## 2. ExpArgs/Agent 需要使用者实现的内容

要实例化并运行 `ExpArgs`，使用者必须提供：
- `env_args: EnvArgs`：任务名称、seed、最大步数、窗口尺寸、slow_mo、是否 headless 等。
- `agent_args: AbstractAgentArgs` 实例，且其 `make_agent()` 必须返回实现了 `browsergym.experiments.Agent` 接口的 Agent。

自定义 Agent 需满足（按类层级拆解）：

1) 继承 `AbstractAgentArgs` 的参数类（负责产出 Agent 实例）
- 关键方法：`make_agent(self) -> Agent`
   - 作用：构造并返回你的 Agent 实例。
- 常见属性：自定义的模型/配置句柄（如 `llm`、`flags`、超参等），在 `__init__` 中注入后在 `make_agent` 里传给 Agent。

2) 继承 `Agent` 的实际 Agent 类（核心逻辑在这里）
- 重要属性：
   - `action_set`：决定动作空间与解析方式。
      - 默认 `HighLevelActionSet` 支持 `click("bid")`、`fill("bid", "text")`、`press("Enter")` 等；经 `action_set.to_python_code` 映射为环境可执行动作。
      - 如需坐标/低层动作，可换用自定义 `ActionSet`，但要确保生成的动作字符串能被对应 parser 解析。
   - 其他在 `__init__` 中注入的依赖（如 `llm`、记忆模块、检索器等）。
- 关键方法：
   - `obs_preprocessor(self, obs)`（可选重写）：
      - 默认会将 DOM/AXTree 转文本并裁剪字段，便于 LLM 消化。
      - 可在此添加检索结果、记忆、页面摘要等；返回的 dict 会被写入轨迹，注意体积（截图不要重复嵌入）。
   - `get_action(self, obs) -> tuple[str, AgentInfo]`（必须实现）：
      - 返回值第一项：动作字符串（None 表示截断 episode）。
      - 返回值第二项：`AgentInfo`，用于日志/统计，字段可含：
         - `think`：链式思考文本。
         - `chat_messages`：LLM 对话的原始消息列表，用于事后分析与 token 统计。
         - `stats`：自定义指标（token 数、重试次数、解析耗时等）。
         - `extra_info`：附加结构化信息（工具调用、中间规划）。
         - `markdown_page` / `html_page`：用于 tape/xray 可视化（可选）。

最小可运行自定义 Agent 示例（文本 LLM，沿用默认高层动作）：

```python
from browsergym.experiments import Agent, AbstractAgentArgs
from browsergym.experiments.agent import AgentInfo, DEFAULT_ACTION_SET, DEFAULT_OBS_PREPROCESSOR

class MiniAgentArgs(AbstractAgentArgs):
      def __init__(self, llm):
            self.llm = llm
      def make_agent(self):
            return MiniAgent(self.llm)

class MiniAgent(Agent):
      def __init__(self, llm):
            self.llm = llm
            self.action_set = DEFAULT_ACTION_SET
      def obs_preprocessor(self, obs):
            return DEFAULT_OBS_PREPROCESSOR(obs)
      def get_action(self, obs):
            prompt = build_prompt(obs)  # 用户实现
            raw = self.llm(prompt)
            action = parse_action(raw)  # 确保符合 action_set 解析规则
            info = AgentInfo(
                  think=extract_thought(raw),
                  chat_messages=[prompt, raw],
                  stats={"prompt_tokens": len(prompt)},
            )
            return action, info
```

补充实践要点：
- 解析严格性：必须生成 `action_set` 可识别的字符串；可加正则或语法解析，错误时重试或返回 None 结束。
- 截断策略：返回 None 即刻结束当前 episode，summary 会标记 truncated。
- 性能与体积：`obs_preprocessor` 返回的内容会写盘，避免放入过大的文本或二进制；截图由框架单独存储。
- 日志可观测性：`think` 和 `chat_messages` 会进入 `experiment.log` 和 `StepInfo`，便于事后调试。

限制与注意：
- 动作字符串必须能被动作集合解析；对 HighLevelActionSet，格式应符合 `highlevel_action_parser` 规则。
- 若需要视觉输入，Agent 自行决定是否使用观测中的 screenshot/HTML/AXTree；框架不自动裁剪。
- 任何异常未捕获会被记录到 summary，并在 debug 模式下抛出。

## 3. 现有示例：GenericAgent 流程

`webarena/agents/legacy/agent.py` 中的 `GenericAgent`：
- `GenericAgentArgs.make_agent()` 返回 `GenericAgent`。
- 初始化时构建 `chat_llm`、设置 `action_set`、检查是否支持视觉。
- `get_action()` 里：基于历史构造 prompt，调用 LLM，解析成动作字符串与思考/记忆；返回 `(action, agent_info)`。

该示例可作为最小实现参考，但已标注 deprecated，可按需裁剪。

## 4. 在当前框架下实现一个 ReAct Agent 的思路

目标：在每步里先生成思考（Reasoning）再给出动作（Act），并保持可解析的动作字符串。

实现步骤：
1. 定义 AgentArgs
   - 继承 `AbstractAgentArgs`，实现 `make_agent()` 返回自定义 ReActAgent。
2. 定义 ReActAgent（继承 `Agent`）
   - `__init__`：注入 LLM/工具、动作集合（默认 HighLevelActionSet 即可）。
   - `obs_preprocessor`：可直接复用默认 DOM/AXTree 展平逻辑，或增加检索信息。
   - `get_action(obs)`：
     - 构造包含历史思考/动作/奖励的 prompt，指示模型先输出思考，再输出一个高层动作（如 `click("bid")`）。
     - 解析模型输出：拆出 `think` 与 `action` 字符串；保证动作可被 `action_set` 解析。
     - 返回 `action, {"think": think_text, "chat_messages": [...], "stats": {...}}`。
   - 可选：若解析失败，返回 None 或重试；返回 None 会使循环截断。

示例框架（伪代码）：

```python
from browsergym.experiments import Agent, AbstractAgentArgs
from browsergym.experiments.agent import AgentInfo, DEFAULT_ACTION_SET, DEFAULT_OBS_PREPROCESSOR

class ReActAgentArgs(AbstractAgentArgs):
    def __init__(self, llm):
        self.llm = llm
    def make_agent(self):
        return ReActAgent(self.llm)

class ReActAgent(Agent):
    def __init__(self, llm):
        self.llm = llm
        self.action_set = DEFAULT_ACTION_SET  # 或自定义
    def obs_preprocessor(self, obs):
        return DEFAULT_OBS_PREPROCESSOR(obs)
    def get_action(self, obs):
        prompt = build_react_prompt(obs)  # 用户实现
        raw = self.llm(prompt)
        think, action = parse_react_output(raw)  # 用户实现，action需可解析
        info = AgentInfo(think=think, chat_messages=[prompt, raw])
        return action, info
```

提示：
- `build_react_prompt` 应明确要求输出格式，如“Thought: ...\nAction: click("bid")”。
- `parse_react_output` 需健壮，确保动作合法；不合法时可返回 None 触发截断或重试。
- 如需统计或可视化，可在 `info.stats` / `info.extra_info` 中填充自定义字段。

## 5. 使用者最小实现清单

- 提供 `EnvArgs`：任务名、步数、headless、slow_mo 等。
- 提供 `AgentArgs.make_agent()`：返回实现 `get_action()` 的 Agent。
- Agent 要求：
  - 选择/实现 `action_set` 并确保动作字符串可解析。
  - （可选）`obs_preprocessor`，处理观测为模型输入。
  - 在 `agent_info` 中写入 `think`/`chat_messages`/`stats` 以便日志与评估。
- 运行：实例化 `ExpArgs(env_args=..., agent_args=...)`，调用 `prepare(Path("./results"))` 后 `run()` 即可。
