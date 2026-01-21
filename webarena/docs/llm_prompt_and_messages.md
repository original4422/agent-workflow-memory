
# WebArena：LLM Prompt 组装与 Messages 维护（Legacy Agent）

本文聚焦 **legacy agent 路径**（`webarena/run.py` + `webarena/agents/legacy/agent.py`），回答：

1. 调用 LLM 的各种 prompt（system prompt / user prompt）如何组建？
2. call LLM 时的 `messages` 如何构成？
3. 每次调用前后的 `messages` 如何维护（重试、日志、落盘）？

说明：仓库里还有其它“直接 OpenAI SDK 调用”的 demo/脚本（例如 `webarena/agents/basic/agent.py`、`webarena/induce_prompt.py`）。它们的 message 结构更简单，但不代表主流程。

---

## 0. 一句话总览（Legacy Agent 的一次 step）

一次 step 内，LLM 相关数据流大致是：

1) `GenericAgent.get_action()` 用 `dynamic_prompting.MainPrompt(...)` 生成「user prompt」（可能包含 screenshot）

2) 同时生成「system prompt」（再拼接 workflow 文本）

3) 组装为 `chat_messages = [SystemMessage(system), HumanMessage(user)]`

4) 调 `retry(chat_llm, chat_messages, ...)`；内部可能多轮「assistant → user(retry)」追加到同一个 list

5) `conversation_logger` 按 step/call 记录每次请求/响应；实验结束时落到 `conversation_history.json`

关键入口与实现：

- Prompt 生成与 call 前组装：`GenericAgent.get_action()` [webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L80-L167)
- Prompt 元件与拼接逻辑：`SystemPrompt`/`MainPrompt`/`History` [webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L180-L693)
- 重试与 messages 追加：`retry(...)` [webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L31-L206)
- LLM 调用日志/落盘：`append_event(...)` / `finalize_conversation_history()` [webarena/conversation_logger.py](../conversation_logger.py#L21-L332)

---

## 1. Prompt 是如何组建的？（system / user）

### 1.1 System prompt（system message 的 content）

在 legacy agent 里，system prompt 的来源非常直接：

- 基础 system prompt：`dynamic_prompting.SystemPrompt().prompt`
- 可选注入 workflow（长期策略/规则）：如果 `Flags.workflow_path` 不为 `None`，则追加该文件内容

对应代码：

- system prompt + workflow 拼接：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L122-L125)
- `SystemPrompt` 内容定义：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L359-L365)
- `Flags.workflow_path` 字段：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L26-L61)

在默认运行入口中，`workflow_path` 由 CLI 传入并写入 `Flags(...)`：

- `--workflow_path` 参数：[webarena/run.py](../run.py#L110-L147)
- 写入 `Flags(workflow_path=...)`：[webarena/run.py](../run.py#L220-L246)

也就是说 system message 的 content = `SystemPrompt` +（可选）workflow 文件内容。

### 1.2 User prompt（human/user message 的 content）

user prompt 在 legacy agent 中由 `dynamic_prompting.MainPrompt` 组装，它是一个由多个 `PromptElement`/`Shrinkable` 组成的“拼装体”。核心是 `MainPrompt._prompt`。

入口：

- 构建 `MainPrompt`：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L99-L107)
- 生成最终 prompt（含 token 适配）：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L109-L120)

#### 1.2.1 指令区（Instructions）：Goal 模式 vs Chat 模式

- 如果 `flags.enable_chat=True`：使用 `ChatInstructions(obs_history[-1]["chat_messages"])`
- 否则：使用 `GoalInstructions(obs_history[-1]["goal"])`

对应代码：

- `MainPrompt` 选择 instructions 的逻辑：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L366-L392)
- `ChatInstructions` 文本模板：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L329-L357)
- `GoalInstructions` 文本模板：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L315-L328)

注意：这里的 `obs_history[-1]["chat_messages"]` 是 **环境 obs 里带来的对话历史**（不是 LLM API 的 OpenAI messages 格式）。`ChatInstructions` 会把它“渲染”为 prompt 中的 bullet 列表。

#### 1.2.2 观测区（Observation）：HTML / AXTree / Error / Screenshot

`Observation` 会把当前 step 的网页状态（HTML/AXTree/错误）拼进 prompt：

- HTML：来自 `obs[flags.html_type]`（常见是 `pruned_html`）
- AXTree：来自 `obs["axtree_txt"]`
- Error：来自 `obs["last_action_error"]`

对应代码：

- `Observation` 组装与输出：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L245-L286)

如果 `flags.use_screenshot=True`，`Observation.add_screenshot()` 会把 prompt 从 `str` 升级为 multi-part content：

- 先把文本 prompt 包进 `[{"type":"text","text": ...}]`
- 再 append `{"type":"image_url", "image_url": {"url": "data:...base64,..."}}`

对应代码：

- screenshot 注入：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L287-L299)

这也是为什么后续的 messages content 可能是 `str` 或 `list[dict]`（用于视觉模型）。

#### 1.2.3 历史区（History）：过去 steps 的 diff / action / memory

如果 `flags.use_history=True`，`History` 会遍历 `obs_history/actions/memories`，为每一步构造 `HistoryStep`，其中可以包含：

- HTML diff、AXTree diff（当 `flags.use_diff=True`）
- 过去 action（当 `flags.use_action_history=True`）
- 过去 memory（当 `flags.use_memory=True` 且 memory 非空）

对应代码：

- `History` 主体：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L661-L693)
- `HistoryStep` 输出（包含 Action/Memory）：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L605-L659)

这些历史信息的“状态维护”来源于 agent 自己的字段（见第 3.4 节）。

#### 1.2.4 动作空间与输出格式提示（ActionSpace + Think/Memory）

`MainPrompt` 里还会拼上：

- Action space 描述 + 示例（要求模型输出 `<action>...</action>`）
- 可选 `<think>...</think>`（当 `flags.use_thinking=True`）
- 可选 `<memory>...</memory>`（当 `flags.use_memory=True`）

对应代码：

- `MainPrompt._prompt` 把 action_space/think/memory 串起来：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L396-L437)
- `ActionSpace` 及其 parse 约束：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L440-L507)

### 1.3 Token 适配（fit_tokens）

legacy agent 在 call LLM 之前会进行 token 预算：

- 预算来源：`flags.max_prompt_tokens`、`chat_model_args.max_total_tokens`、`chat_model_args.max_input_tokens` 取最小非空值
- 如果超限，则对 `MainPrompt` 执行多轮 shrink（主要截断 HTML/AXTree/History diff）

对应代码：

- 预算计算 + 调用 `fit_tokens`：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L109-L120)
- shrink 核心逻辑：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L180-L235)

---

## 2. call LLM 时的 messages 如何构成？

### 2.1 Legacy Agent：LangChain BaseMessage 列表

在 `GenericAgent.get_action()` 里，messages 初始是两条：

- `SystemMessage(content=sys_msg)`
- `HumanMessage(content=prompt)`

对应代码：

- messages 组装：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L126-L129)

这里的 `prompt` 可能是：

- `str`（纯文本）
- `list[dict]`（文本 + image_url），来自 `Observation.add_screenshot()`（见第 1.2.2）

### 2.2 CloudGPT（Azure OpenAI）路径：最终转成 OpenAI `{role, content}`

当 `ChatModelArgs.make_chat_model()` 走到 `CloudGPTChatModel` 时（model_name 前缀为 `cloudgpt/` 或 `azure/`）：

- `_call()` 中会把 LangChain messages 转成 OpenAI 风格 dict list：`openai_messages = _convert_messages_to_dict(messages)`
- 然后 `client.chat.completions.create(model=..., messages=openai_messages, ...)`

对应代码：

- CloudGPT `_call` 与 `openai_messages`：[webarena/agents/legacy/utils/chat_api.py](../agents/legacy/utils/chat_api.py#L356-L390)
- `_convert_messages_to_dict`（system/user/assistant 映射）：[webarena/agents/legacy/utils/chat_api.py](../agents/legacy/utils/chat_api.py#L448-L489)

### 2.3 LangChain OpenAI 路径：`chat.invoke(messages)`

当 `ChatModelArgs.make_chat_model()` 返回 `langchain_openai.ChatOpenAI`（openai/glm/kimi 等）时，真正的调用发生在 `retry()` 内：

- `answer = chat.invoke(messages)`

对应代码：

- `retry` 内 invoke：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L110-L118)

---

## 3. messages 在每次调用前后如何维护？（重试 + 日志 + 落盘）

这里有两层“维护”：

- A) **为了让 LLM 改正输出**：在同一个 `messages` list 上 append（形成多轮对话）
- B) **为了可观测性/复盘**：把每次请求与响应的 messages 记录到 `conversation_history.json`

### 3.1 A 层：`retry()` 如何在同一个 list 上追加 messages

在 legacy agent 中，`chat_messages` 是一个可变 list，被传入 `retry(self.chat_llm, chat_messages, ...)`。

`retry()` 的行为：

1. 调用：`answer = chat.invoke(messages)`
2. 追加 assistant：`messages.append(answer)`
3. parser 校验。如果不合法：再追加一条“用户纠错提示”
	 - `messages.append(HumanMessage(content=retry_message))`
4. 再次回到 1，直到成功或超过次数

对应代码：

- `messages.append(answer)`：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L183-L189)
- `messages.append(HumanMessage(...))`：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L190-L194)

因此，在一次 step 内最终的 messages 形态通常是：

- 第 0 次：`[system, user]`
- 第 1 次失败后：`[system, user, assistant, user(retry)]`
- 第 2 次失败后：`[system, user, assistant, user(retry), assistant, user(retry)]`
- ...

并且，在成功之后，`GenericAgent` 会把这份 messages 的内容附到 `ans_dict` 里用于调试：

- `ans_dict["chat_messages"] = [m.content for m in chat_messages]`

对应代码：

- 输出到 `ans_dict`：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L160-L164)

注意：这里保存的是 `m.content`，不会保留 role；role 信息主要在 conversation_logger 的结构化日志里。

### 3.2 B 层：conversation_logger 如何记录“每一次 LLM 请求”

#### 3.2.1 step/call 编号如何维护

每个环境 step 开始时：

- `conversation_logger.set_step_idx(len(self.obs_history) - 1)`
- `conversation_logger.reset_call_idx()`

对应代码：

- step 开始时重置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L96-L98)

`conversation_logger.append_event()` 内部会 `next_call_idx()`，从 0 开始递增。

对应代码：

- call idx 递增：[webarena/conversation_logger.py](../conversation_logger.py#L33-L41)
- append_event 使用 step/call：[webarena/conversation_logger.py](../conversation_logger.py#L212-L260)

#### 3.2.2 记录的 messages 是什么格式？

`append_event(messages=...)` 接受的 messages 可以是：

- OpenAI dict list（如 `[{role, content}, ...]`）
- LangChain message 对象 list（如 `SystemMessage/HumanMessage/AIMessage`）

它会做两步处理：

1) `normalize_messages()`：统一成 `[{role, content}, ...]`

- dict 直接透传 role/content
- LangChain 根据 `msg.type` 映射到 role，并取 `msg.content`

对应代码：

- normalize：[webarena/conversation_logger.py](../conversation_logger.py#L99-L135)

2) `sanitize_messages()`：对 `content` 里可能出现的 `image_url.data:...base64...` 做落盘与替换

- 把 data URL 解码写到 `results/.../images/step_{s}_call_{c}_*.{png|jpg|...}`
- 在 JSON 里把该 part 替换为 `{"type":"image_ref", "ref": {"path": "images/..." ...}}`

对应代码：

- sanitize（含 image_url→image_ref）：[webarena/conversation_logger.py](../conversation_logger.py#L137-L210)

#### 3.2.3 谁在调用 append_event？（不同 provider）

- 对 LangChain OpenAI 路径（`ChatOpenAI`）：`retry()` 在成功/异常/限流时都会 append_event（provider=`langchain_openai`）

对应代码：

- `retry()` 的 append_event：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L120-L179)

- 对 CloudGPT Azure 路径（`CloudGPTChatModel`）：在 `_call()` 里 append_event（provider=`cloudgpt_aoai`）

对应代码：

- CloudGPT `_call()` append_event：[webarena/agents/legacy/utils/chat_api.py](../agents/legacy/utils/chat_api.py#L401-L439)

### 3.3 conversation_history.json 如何生成（落盘/合并）

实验开始前，`run.py` 会把实验目录写到环境变量，供 logger 在 runtime 找到输出位置：

- `WEBARENA_EXP_DIR = exp_args.exp_dir`

对应代码：

- 设置 env var：[webarena/run.py](../run.py#L248-L258)

`append_event()` 会把每条 event 以 JSONL 追加到：

- `results/.../conversation_history.<pid>.jsonl.tmp`

最终在 `exp_args.run()` 结束后调用 `finalize_conversation_history()`：

- 收集所有 `conversation_history.*.jsonl.tmp`
- 合并、按 `(step_idx, call_idx, ts)` 排序
- 输出 `conversation_history.json`

对应代码：

- finalize 调用：[webarena/run.py](../run.py#L272-L276)
- finalize 实现：[webarena/conversation_logger.py](../conversation_logger.py#L267-L332)

### 3.4 另一个层面的“状态维护”：obs_history/actions/memories/thoughts

除了 LLM API 的 messages，legacy agent 还维护了用于 prompt 生成的跨 step 状态：

- `self.obs_history.append(obs)`：每 step 追加观测
- 每 step 结束后：`self.actions.append(...)`、`self.memories.append(...)`、`self.thoughts.append(...)`

对应代码：

- obs_history 追加：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L92-L99)
- action/memory/thought 追加：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L152-L159)

这些状态会在下一次 step 重新喂给 `MainPrompt(...)`，从而影响第 1 节的 prompt 组装。

---

## 4. 对照：非主流程（更“直接”的 messages）

如果你想看最简单的 OpenAI Chat messages 长什么样：

- 最简 agent demo：直接 `messages=[{"role":"system"...}, {"role":"user"...}]`
	- [webarena/agents/basic/agent.py](../agents/basic/agent.py#L44-L74)

- workflow 归纳脚本：只有 user role，没有 system role
	- [webarena/induce_prompt.py](../induce_prompt.py#L86-L100)

这些文件有助于理解 OpenAI SDK 的 messages 结构，但它们不包含 legacy agent 的重试与 conversation logging 机制。

---

## 5. 补充问答：信息从哪来 / message 如何构成 / response 如何处理

本节以 legacy agent 的主流程为准（`webarena/agents/legacy/agent.py`），把常见问题按“信息来源 → messages → response 处理与执行”串起来。

### 5.a LLM 使用的信息从何而来？

#### 5.a.i action_set 是如何获取到的？又是如何告诉 LLM 的？（放在 message 哪部分？）

**action_set 的来源（运行时选择）**

- CLI 入口 `webarena/run.py` 通过 `--action_space` 指定动作空间类型（如 `bid`、`coord`、`bid+nav` 等）。
	- 参数定义：[webarena/run.py](../run.py#L86-L96)

- legacy agent 初始化时会把 `flags.action_space` 映射为 BrowserGym 的 `AbstractActionSet` 实例：
	- `GenericAgent.__init__` 里设置：`self.action_set = dynamic_prompting._get_action_space(self.flags)`
		- 代码位置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L65-L76)
	- 映射逻辑本身在 `_get_action_space(flags)`：按 `flags.action_space` 选择 `PythonActionSet` 或 `HighLevelActionSet(subsets=...)`。
		- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L474-L509)

**action_set 是如何“告诉 LLM”的（属于 user prompt / HumanMessage）**

- `MainPrompt` 在生成 user prompt 时，会把 `ActionSpace` 这一段拼进 prompt 文本（`# Action space:` + `action_space.describe()` + 示例 action）。
	- `MainPrompt._prompt` 把 `self.action_space.prompt` 拼到最终 prompt 中：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L374-L426)
	- `ActionSpace.__init__` 构造 `# Action space:\n{describe()}` 与 `<action>...</action>` 示例：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L440-L457)

- 在 LLM API 的 messages 结构上：Action space **不在 system message**，而是作为 user message content 的一部分（`HumanMessage(content=prompt)`）。
	- messages 组装位置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L117-L131)

#### 5.a.ii web 的页面信息有哪些？如何获取到的？又是如何告诉 LLM 的？

**页面信息有哪些（在 prompt 中的 Observation 区）**

- HTML（默认是 `pruned_html`，也可能切换为其它 `flags.html_type`）
- 可访问性树 AXTree（文本化后的 `axtree_txt`，可选择是否带坐标）
- 上一步 action 的报错日志（`last_action_error`，可选）
- 截图（`screenshot`，可选；视觉模型走 multi-part content）

对应 prompt 组装：`Observation` 会把这些字段渲染为 `# Observation of current step:` 段，并在开启截图时把 prompt 从 `str` 升级为 `[{type:text}, {type:image_url}]`。

- `Observation` 读取 `obs[flags.html_type]`、`obs["axtree_txt"]`、`obs["last_action_error"]` 并构造 prompt：
	- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L256-L286)
- `Observation.add_screenshot()` 注入 `image_url(data:...base64,...)`：
	- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L287-L299)

**这些页面字段是如何获取到的（来自 env obs + agent 的 obs_preprocessor）**

- 环境每一步会返回一个 observation dict；legacy agent 通过 `obs_preprocessor()` 把结构化 DOM/AXTree 转成可喂给 LLM 的文本字段：
	- `dom_txt = flatten_dom_to_str(obs["dom_object"], ...)`
	- `axtree_txt = flatten_axtree_to_str(obs["axtree_object"], ...)`
	- `pruned_html = prune_html(dom_txt)`
	- 代码位置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L36-L61)

**如何“告诉 LLM”（属于 user prompt / HumanMessage）**

- 这些页面信息最终都被拼接进 `prompt = fit_tokens(MainPrompt(...))`，并作为 `HumanMessage(content=prompt)` 的 content 发送。
	- 代码位置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L93-L131)

### 5.b 每次调用 LLM 时传入的 message 是如何构成的？

**一次 step 的第 1 次调用（初始 messages）**

- system：`SystemPrompt().prompt` +（可选）workflow 文件内容
- user：`MainPrompt` 渲染出的完整 prompt（包含 instructions/observation/history/action space/think/memory 等；可能含截图 multi-part content）

对应代码：

- system prompt + workflow 拼接：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L117-L125)
- 初始 messages 列表 `[SystemMessage, HumanMessage]`：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L126-L131)

**同一个 step 内的重试调用（messages 会“变长”）**

当解析失败时，`retry()` 会在同一个 `messages` list 上追加：

1) 追加 assistant 原始回答（`messages.append(answer)`）
2) 追加一条 user 的纠错/重试提示（`messages.append(HumanMessage(content=retry_message))`）

- 追加 assistant + 追加 retry user message：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L175-L194)

这也是为什么一次 step 内的 messages 会从 `[system, user]` 变成：

- `[system, user, assistant, user(retry), assistant, user(retry), ...]`

### 5.c 如何对 response 进行处理？

#### 5.c.i 拿到 response 后会进行什么解析吗？

解析发生在 `GenericAgent.get_action()` 里传给 `retry()` 的 `parser()`：

- `parser()` 调用 `main_prompt._parse_answer(text)`：解析 `<think>`、`<memory>`（可选）与 `<action>`（必需）。
	- `GenericAgent.get_action()` 的 parser 定义：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L133-L147)
	- `MainPrompt._parse_answer()` 聚合 think/memory/action 的解析：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L428-L437)

底层解析规则：

- 通过正则提取形如 `<action>...</action>` 的 tag 内容；缺失必需 tag 会返回 `retry_message`（例如 `Missing the key <action> in the answer.`）。
	- `parse_html_tags_raise()` + `parse_html_tags()`：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L434-L487)

另外，action 会做一次“能否映射到可执行 python 动作”的校验：

- `ActionSpace._parse_answer()` 调 `self.action_space.to_python_code(ans_dict["action"])`，只做校验不改写 action 文本；失败会抛 `ParseError`。
	- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L458-L472)

#### 5.c.ii 如何执行 response 给出的 action 的？

执行链路是：agent 产出 action 字符串 → BrowserGym loop 把 action 发给 env.step（内部用 action_mapping 转成可执行动作并驱动浏览器）。

- loop 创建环境时把 `agent.action_set.to_python_code` 作为 `action_mapping` 注入环境：
	- 代码位置：[myenv/webarena/lib/python3.10/site-packages/browsergym/experiments/loop.py](../../myenv/webarena/lib/python3.10/site-packages/browsergym/experiments/loop.py#L397-L406)
- 每一步执行时直接 `env.step(action)`：
	- 代码位置：[myenv/webarena/lib/python3.10/site-packages/browsergym/experiments/loop.py](../../myenv/webarena/lib/python3.10/site-packages/browsergym/experiments/loop.py#L187-L201)

legacy agent 自身只负责返回 action：

- `return ans_dict["action"], ans_dict`：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L176-L179)

#### 5.c.iii 当 response 解析错误时，是如何处理的？此时再调用 LLM 时，message 如何构成？

**解析错误如何触发重试**

- 如果 `main_prompt._parse_answer()` 抛出 `ParseError`，`parser()` 会把它转成 `(None, False, str(e))` 交给 `retry()` 处理。
	- 代码位置：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L133-L145)

**重试时 messages 如何构成（是否把错误信息放到 message 里？）**

- 是的：错误信息会被作为一条新的 **user message** 追加到 messages 中（`HumanMessage(content=retry_message)`）。不会额外加新的 system message。
	- 追加逻辑：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L183-L194)

这里的 `retry_message` 可能来自两类：

- tag 缺失/重复等格式错误（例如缺 `<action>`）：由 `parse_html_tags()` 生成的 `retry_message`。
	- 代码位置：[webarena/agents/legacy/utils/llm_utils.py](../agents/legacy/utils/llm_utils.py#L458-L487)
- action 不在允许动作空间内/无法映射：由 `ActionSpace._parse_answer()` 抛出的 `ParseError("Error while parsing action...")`。
	- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L458-L472)

**超过最大重试次数**

- `retry()` 最终会抛 `ValueError`；`GenericAgent.get_action()` 捕获后返回 `action=None`，并把错误信息与堆栈记录到 `ans_dict`。
	- 捕获与降级返回：[webarena/agents/legacy/agent.py](../agents/legacy/agent.py#L155-L175)

### 5.d 不同 action_space 的区别与示例

`action_space` 决定了 Agent 可用的动作集合。WebArena 基于 BrowserGym 实现了多种动作空间，通过 `--action_space` 参数进行配置。

#### 5.d.i 动作空间类型详解

| 类型 | 包含子集 | 说明 |
| :--- | :--- | :--- |
| `python` | - | **原生 Python 模式**。Agent 直接输出 Playwright 代码。灵活性最高，但对模型编码能力要求极高。 |
| `bid` | `chat`, `bid` | **基于 ID 的高层动作**。使用浏览器生成的 `bid`（Backend ID）来定位元素，如 `click("32")`。 |
| `coord` | `chat`, `coord` | **基于坐标的高层动作**。使用像素坐标操作，如 `click(450, 600)`。适用于无传统 ID 的视觉元素。 |
| `nav` | - | **导航动作**。通常与其他空间组合使用，提供浏览器的前进、后退、刷新、滚动等功能。 |
| `混合模式` | `bid+coord+nav` 等 | **最强组合**。提供最全面的操作手段，是当前 WebArena 评估中的主流配置。 |

#### 5.d.ii 动作示例（LLM 输出格式）

根据 `ActionSpace` 的定义，LLM 返回的动作必须包裹在 `<action>` 标签内。

**1. Python 模式示例**
```python
<action>
page.get_by_role("button", name="Submit").click()
</action>
```

**2. bid 模式示例（最常用）**
```python
<action>
click("32")
</action>
<action>
fill("a12", "WebArena project")
</action>
```

**3. coord 模式示例**
```python
<action>
click(128, 456)
</action>
```

**4. nav 模式示例**
```python
<action>
go_back()
</action>
<action>
scroll(0, 500)
</action>
```

**5. chat 模式示例（与用户交互）**
```python
<action>
answer("I have found the top-5 best selling products for you.")
</action>
```

#### 5.d.iii 官方引用与背景

WebArena 官方已将底层架构迁移至 [BrowserGym](https://github.com/ServiceNow/BrowserGym)，这使得动作空间更加标准化和可扩展。

- **官方文档说明**：参考 [WebArena 仓库 README](https://github.com/web-arena-x/webarena#quick-walkthrough) 中提到的 `create_id_based_action` 与 `observation_type`。
- **BrowserGym 集成**：本地代码 `_get_action_space` 逻辑清晰展示了子集（subsets）的组合方式。
	- 代码位置：[webarena/agents/legacy/dynamic_prompting.py](../agents/legacy/dynamic_prompting.py#L474-L509)

