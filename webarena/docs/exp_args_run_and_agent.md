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

### 2.1 `EnvArgs` 关键字段速查（重点：`headless` / `viewport` / `slow_mo`）

在本仓库的入口脚本中（见 `webarena/run.py`），`EnvArgs` 通常像下面这样构造：

```python
env_args = EnvArgs(
      task_name=args.task_name,
      task_seed=None,
      max_steps=args.max_steps,
      headless=args.headless,
      viewport={"width": 1500, "height": 1280},
      slow_mo=args.slow_mo,
      task_kwargs=task_kwargs,
)
```

你可以把 `EnvArgs` 理解成“环境工厂”的参数：它决定 BrowserGym/WebArena 运行时浏览器如何启动、页面如何渲染、以及每一步交互的节奏。

#### `headless`

- **含义**：是否以无头模式（headless）启动浏览器。
   - `True`：不显示浏览器窗口（更适合批量跑实验、CI、远程机器）。
   - `False`：显示真实窗口（更适合调试、观察 Agent 行为）。
- **影响点**：
   - **可观测性**：`headless=False` 你能直接看到页面、弹窗、跳转、滚动等；对排查 action 解析错误、元素不可点击、焦点丢失非常有帮助。
   - **稳定性差异**：某些网站/渲染路径在 headless 与 headed（有界面）下可能存在轻微差异（例如字体渲染、动画节奏、窗口焦点、权限提示等），建议在“最终评测配置”与“调试配置”之间保持一致或至少做一次对齐验证。
   - **资源开销**：有窗口通常更占用桌面资源；无头通常更节省。

#### `viewport`

- **含义**：浏览器视口大小（单位：像素），影响页面的响应式布局、可见区域、滚动长度，以及截图/DOM/AXTree 中的可见内容分布。
   - 典型格式：`{"width": 1500, "height": 1280}`。
- **为什么重要**：
   - **响应式布局**：同一网站在不同宽度下可能切换为移动端布局/桌面布局（导航栏折叠、按钮位置变化、需要展开菜单等），直接影响 Agent 的可达性与策略。
   - **动作空间相关**：如果你使用/计划使用坐标类动作（`coord` 等），viewport 变化会直接改变坐标系与元素位置；即使是 `bid`（基于元素 id）动作，viewport 也会影响元素是否在可视区域、是否需要滚动才能交互。
   - **复现性**：数据集生成/评测时，建议固定 viewport，避免同一任务在不同机器/配置下出现布局差异导致轨迹不可复现。

#### `slow_mo`（重点）

- **含义**：对浏览器自动化动作的“慢动作”延迟（slow motion）。在 Playwright 语义中，通常表示**每个底层操作之间额外等待的时间**。
- **单位**：一般是 **毫秒（ms）**。
   - 例如 `slow_mo=30` 约等于每个 Playwright 动作额外延迟 30ms。
   - `slow_mo=0` 表示不额外放慢。

##### `slow_mo` 到底会“慢”哪些东西？

它主要影响 **Playwright 发出的自动化指令节奏**，常见包括（举例而非穷举）：

- 点击（click）、双击（dblclick）、输入（type/fill）、按键（press）、滚动（scroll）、鼠标移动（move）等
- 以及很多由这些高层动作分解出来的底层事件序列

注意：
- `slow_mo` **不是**“网络慢一点/页面加载慢一点”。它不会改变服务器响应速度，但会让你的自动化操作更慢。
- `slow_mo` 也 **不是**“显式等待（wait）”的替代品：如果页面需要等待某个元素出现/某个请求完成，正确做法仍是使用框架/任务内的等待机制；`slow_mo` 只能降低“操作太快导致 race condition”的概率，不能保证同步。

##### 为什么 `slow_mo` 对调试特别有用？

- **看得清楚**：尤其当 `headless=False` 时，`slow_mo` 能让你肉眼跟上 Agent 的行为（例如 200~800ms 会非常直观）。
- **降低时序敏感问题**：有些页面动画/渲染/焦点切换需要一点时间，操作过快可能出现：
   - 点击发生但页面还没完成重排，导致下一步找不到元素
   - 输入框未获得焦点就开始输入
   - 刚滚动完立即点击，点击落点被遮挡/偏移

##### 什么时候不建议把 `slow_mo` 开太大？

- **吞吐量**：`slow_mo` 会线性拉长一次 episode 的真实耗时（wall-clock time）。如果你的 action 链很长或 multi-actions 很多，`slow_mo=500` 这类值会让实验变得非常慢。
- **掩盖真实问题**：过大的 `slow_mo` 可能“偶然”让页面赶上节奏，从而掩盖了缺少等待/错误同步的根因；建议：
   - 调试阶段可以开大定位问题
   - 定型后逐步降到 `0~50ms`，用更合理的等待/重试策略保证稳定

##### 实用调参建议（经验法则）

- **批量跑数据/评测**：优先 `slow_mo=0` 或 `slow_mo=10~30`（本仓库默认 `30`）。
- **交互调试（看动作）**：`slow_mo=200~800`（配合 `headless=False`）。
- **定位时序 bug**：先 `slow_mo=500` 看现象，再降回小值验证是否仍稳定；如果降回去就不稳定，优先补“显式等待/条件等待”而不是长期依赖 `slow_mo`。

##### 与其它参数的关系

- 与 `headless`：`headless=False` + 较大 `slow_mo` 是最直观的调试组合；`headless=True` 时 `slow_mo` 仍生效，但你只能通过日志/截图观察。
- 与 `max_steps`：`max_steps` 限制的是**交互步数**，不是总时长；但 `slow_mo` 会显著增加每步的真实耗时，导致一次任务跑很久（尤其 multi-actions）。
- 与录屏/截图：`slow_mo` 会让录屏更“可读”，但也会让文件更长、生成更慢。

> 小结：`slow_mo` 的定位更像“调试旋钮”和“节奏稳定器”。它能缓解一部分时序敏感问题，但不应替代正确的等待/同步策略。

#### `task_seed`

- **含义**：任务随机种子（seed），用于控制任务初始化中的随机性（例如初始状态/干扰项/采样配置等，具体取决于任务实现）。
- **典型用法**：
   - `task_seed=None`：不显式固定种子（通常意味着每次运行可能略有不同，或由框架/任务默认策略决定）。
   - `task_seed=<int>`：固定任务初始化的随机性，便于**复现同一任务**与对比不同 Agent/Prompt 的效果。
- **实践建议**：
   - 做 ablation 或回归测试时，建议固定 `task_seed`；做大规模采样生成数据时，可以让 seed 随机或按任务 id/日期编码。

#### `task_kwargs`（重点）

- **含义**：传给“具体 task”的额外初始化参数（keyword arguments）。
   - 你可以把它理解成：`task_name` 只能告诉环境“跑哪个任务”，而 `task_kwargs` 则进一步告诉任务“用什么初始条件/额外配置启动”。
- **在本仓库里的关键例子**：`openended` 任务需要指定起始 URL。

   在 `webarena/run.py` 中有明确分支：

   - 当 `args.task_name == "openended"`：
      - 构造 `task_kwargs = {"start_url": args.start_url}`
      - 传入 `EnvArgs(..., task_kwargs=task_kwargs)`

   直观理解：这相当于告诉 openended 环境“从哪个网页开始”。

##### `task_kwargs` 什么时候会生效？

`task_kwargs` 是否被使用，以及接受哪些 key，**完全由具体任务实现决定**：

- 对 `openended`：你已经看到它期望 `start_url`。
- 对 `webarena.*` 这类任务：多数情况下任务配置来自内置的 `test.raw.json`（或你通过 `--task_config_path` monkeypatch 注入的 JSON）。这些任务通常不需要额外的 `task_kwargs`；即便传了，也可能被忽略或触发校验错误（取决于实现）。

##### 常见坑与最佳实践（重点）

- **不要把“任务配置文件的内容”塞进 `task_kwargs`**：
   - `webarena.*` 的任务定义通常来自 JSON 配置（本仓库支持用 `--task_config_path` 替换读取的 `test.raw.json`）。
   - `task_kwargs` 更适合传“小而明确”的运行时参数（例如 openended 的 `start_url`），而不是整份任务 spec。
- **key 必须被任务识别**：
   - 若任务实现对 `task_kwargs` 做了严格校验，传入未知 key 可能直接报错。
   - 若你不确定该任务支持哪些 key，最可靠的方式是：定位该 task 的构造函数/注册代码，或在框架里搜索它如何消费 `task_kwargs`。
- **保证可复现性**：
   - `task_kwargs` 里如果包含动态值（例如时间戳、随机 URL、临时 token），会显著降低复现性。
   - 如果你在做数据集构建，建议把 `task_kwargs`（尤其是 `start_url` 这类关键字段）也记录到你的任务元数据里。

#### `wait_for_user_message`

- **含义**：是否让环境在某些时刻等待用户消息（更偏“交互式 demo/人工介入”用）。
- **在本仓库里的用法**：
   - 当 `task_name == "openended"` 时，代码会设置：`env_args.wait_for_user_message = True`。
   - 直观效果是：openended 场景更像一个“可聊天/可介入”的浏览器会话，环境可能在关键节点等待外部消息再继续。
- **注意**：这会影响运行时的节奏与可自动化程度；批量评测通常不启用。

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
