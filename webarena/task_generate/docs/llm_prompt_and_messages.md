# task_generate（production）里的 LLM Prompt / Messages 组装与维护

> 目标：解释 **非 legacy 的 `webarena/task_generate`（production）链路**里：
>
> 1. 调用 LLM 的各种 prompt（system prompt / user prompt）如何组建？
> 2. call LLM 时的 messages 如何构成？
> 3. 每次调用前后的 messages 如何维护（重试、跨 step/跨阶段、落盘）？

本文聚焦 `webarena/task_generate` 目录下的三阶段 CuES pipeline（Stage1/2/3）与可选 Query Rewrite。

---

## 0. 一张图：端到端数据流（从入口到落盘）

入口 `main.py` 解析参数、读取配置，然后创建 pipeline 并执行 stage：
- 入口：[`webarena/task_generate/main.py`](../main.py#L1)
- Pipeline：[`webarena/task_generate/src/core/pipeline.py`](../src/core/pipeline.py#L1)

运行过程中，LLM 相关数据大体按下面路径流动：

1. **Prompt builder**（拼 system/user prompt 文本）
   - Stage1：[`ExplorationPrompts`](../src/prompts/exploration.py#L9)
   - Stage2：[`TaskAbstractionPrompts`](../src/prompts/task_abstraction.py#L10)
   - Stage3：[`TrajectoryPrompts`](../src/prompts/trajectory.py#L9)
2. **组装 messages（OpenAI 风格）**：`List[Dict[str, str]]`
   - 通用格式器（可选）：[`PromptManager`](../src/core/api_client.py#L155)
   - 常见就地组装：见各 stage 内的 `messages = [...]`
3. **APIClient 调用 LLM + 重试**
   - [`APIClient.chat_completion`](../src/core/api_client.py#L96)
   - [`APIClient.chat_with_retry`](../src/core/api_client.py#L123)
4. **维护 / 落盘**
   - Stage1/2：将 triplets / tasks 写入 jsonl：[`DataStorage.save_triplet`](../src/data/storage.py#L77), [`DataStorage.save_task`](../src/data/storage.py#L141)
   - Stage3：trajectory 写入 json：[`DataStorage.save_trajectory`](../src/data/storage.py#L205)
   - Stage3 额外把 `messages`（训练数据）嵌入 trajectory：见 [`Stage3TrajectoryGeneration._generate_trajectory`](../src/stages/stage3_trajectory_generation.py#L114)
   - Query Rewrite 使用 trajectory 内的 `messages` 做上下文：[`QueryRewriter._generate_variants`](../src/stages/query_rewrite.py#L122)

---

## 1) system prompt / user prompt 如何组建？

在 production 链路里，prompt 组装是“**按 stage 定制**”的：每个 stage 都有独立的 prompt builder（纯字符串拼装），再交给 stage 组装成 messages。

### 1.1 Stage 1（Curious Exploration）：探索型 prompt

- Prompt builder：[`ExplorationPrompts.build_exploration_prompt`](../src/prompts/exploration.py#L12)
  - system prompt：[`ExplorationPrompts._build_system_prompt`](../src/prompts/exploration.py#L33)
  - user prompt：[`ExplorationPrompts._build_user_prompt`](../src/prompts/exploration.py#L70)

关键输入：
- `current_obs`：当前页面状态（AXTree/DOM 展平文本）
- `history`：最近动作与结果（用于提示模型“别重复”）
- `exploration_memory`：探索记忆（由 MemoryManager LLM 总结而来，跨 step/跨 rollout 有意义）
- `exploration_requirement`：外部指定的探索要求

Stage1 在 [`Stage1Exploration._get_exploration_action`](../src/stages/stage1_exploration.py#L270) 里拿到 `system_prompt/user_prompt` 后组装 messages（见下一节）。

### 1.2 Stage 2（Task Abstraction）：从 triplets 抽象任务

- Prompt builder：[`TaskAbstractionPrompts.build_task_extraction_prompt`](../src/prompts/task_abstraction.py#L13)
  - system prompt（包含 JSON 输出约束与网站类别示例）：[`TaskAbstractionPrompts._build_system_prompt`](../src/prompts/task_abstraction.py#L25)
  - user prompt（包含 env 描述、历史任务记忆、triplet 序列）：[`TaskAbstractionPrompts._build_user_prompt`](../src/prompts/task_abstraction.py#L109)

Stage2 还会引入“任务记忆”（避免重复任务）：
- [`MemoryManager.get_task_memory`](../src/core/memory_manager.py#L61)

### 1.3 Stage 3（Trajectory Generation）：执行任务，生成轨迹

- system prompt：[`TrajectoryPrompts.get_system_prompt`](../src/prompts/trajectory.py#L12)
- action 获取的 messages（system + user）：[`TrajectoryPrompts.build_action_prompt`](../src/prompts/trajectory.py#L44)
- 可选 reflection（如果开启）：[`TrajectoryPrompts.build_reflection_prompt`](../src/prompts/trajectory.py#L99)

注意：Stage3 的 user prompt 通常由：任务描述 + query +（可选 hints）+ history + 当前 observation 组成。

### 1.4 额外：Stage0（概念抽取）与 Query Rewrite 的 prompt

- 概念抽取（可选）：[`CuESPipeline.extract_concepts`](../src/core/pipeline.py#L113)
- Query Rewrite（可选）：[`QueryRewriter._generate_variants`](../src/stages/query_rewrite.py#L122)

这两个都采用“直接拼字符串 + 单条 user message”的方式。

---

## 2) call LLM 时的 messages 如何构成？

production 链路里使用的是 OpenAI / OpenAI-compatible 的 `messages` 结构：

```python
messages = [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
]
```

### 2.1 Stage 1 / Stage 2：固定两条（system + user）

- Stage1 构造 messages：[`Stage1Exploration._get_exploration_action`](../src/stages/stage1_exploration.py#L290)
- Stage2 构造 messages：[`Stage2TaskAbstraction._extract_tasks_from_batch`](../src/stages/stage2_task_abstraction.py#L120)

两者都是把各自 prompt builder 产出的 `system_prompt/user_prompt` 放进两条 message。

### 2.2 Stage 3：两类 messages

**(A) LLM “决策下一步 action”的调用**：每一步都重新构造 `messages = [system, user]` 发送
- 构造 messages：[`Stage3TrajectoryGeneration._get_task_action`](../src/stages/stage3_trajectory_generation.py#L322)
- 具体拼装逻辑在：[`TrajectoryPrompts.build_action_prompt`](../src/prompts/trajectory.py#L44)

**(B) 用于训练数据/后处理的“消息轨迹（messages trace）”**：
- 在每个 env step 后，把 user/assistant 对追加到 `messages` 列表（这不是下一次 LLM 调用的输入，而是“轨迹记录”）
- 初始化与追加：[`Stage3TrajectoryGeneration._generate_trajectory`](../src/stages/stage3_trajectory_generation.py#L128)
  - 初始化 `messages = []`：[`stage3_trajectory_generation.py#L128`](../src/stages/stage3_trajectory_generation.py#L128)
  - 添加 system：[`stage3_trajectory_generation.py#L140`](../src/stages/stage3_trajectory_generation.py#L140)
  - 每步追加 user/assistant：[`stage3_trajectory_generation.py#L218`](../src/stages/stage3_trajectory_generation.py#L218)

这种设计的结果是：
- “用于调用 LLM 的 messages”是 **每步临时生成** 的。
- “用于保存训练数据的 messages”是 **跨步累积** 的，并写入最终 trajectory 文件。

### 2.3 APIClient 端：真实发往模型的内容

最终发送发生在：
- [`APIClient.chat_completion`](../src/core/api_client.py#L96)

它将 `{model, messages, temperature, max_tokens}` 组成参数后调用：
- `self._client.chat.completions.create(**params)`（同文件内实现）

同时支持 OpenAI / Azure / 兼容 API 的 client 初始化：
- [`APIClient._init_client`](../src/core/api_client.py#L39)

### 2.4 PromptManager：可选的 messages 统一格式器

如果希望用一个地方统一格式：
- [`PromptManager.format_system_message`](../src/core/api_client.py#L159)
- [`PromptManager.format_user_message`](../src/core/api_client.py#L164)
- [`PromptManager.build_conversation`](../src/core/api_client.py#L174)

当前实现里，多数 stage 直接手写 `{role, content}` 字典（更直观）。

---

## 3) 每次调用前后的 messages 如何维护？

这里需要区分：
- **调用输入 messages**：传给 `APIClient.chat_with_retry` 的那份。
- **训练/日志 messages**：Stage3 维护并落盘的那份。

### 3.1 重试（retry）期间 messages 是否会变化？

在 production 链路里：
- 重试逻辑在 [`APIClient.chat_with_retry`](../src/core/api_client.py#L123)
- 它会“重复调用 `chat_completion(messages, ...)`”，但 **不会修改 `messages` 列表本身**（无追加、无插入）。

也就是说：
- 如果第一次请求失败，后续重试仍发送同一份 `messages`。
- 与 legacy 链路里“重试时会把 assistant 回复/用户补充提示 append 回 messages”的方式不同。

### 3.2 Stage 内：如何跨 step 维护上下文？

#### Stage 1：不维护“对话 messages”，维护 `history` + `exploration_memory`

- `history`：在 env step 循环中追加 action/observation：[`stage1_exploration.py#L170`](../src/stages/stage1_exploration.py#L170)
- `exploration_memory`：周期性刷新（每 5 步）并写入文件：
  - 刷新触发：[`stage1_exploration.py#L182`](../src/stages/stage1_exploration.py#L182)
  - 生成/更新逻辑：[`MemoryManager.get_exploration_memory`](../src/core/memory_manager.py#L25)
  - 写入 memories：[`memory_manager.py#L57`](../src/core/memory_manager.py#L57)

因此 Stage1 的“上下文”主要靠：
- `history`（短期，提示最近做了什么）
- `exploration_memory`（中期/长期，总结探索覆盖面）

#### Stage 2：同样不维护对话 messages，依赖 `task_memory`

Stage2 是 batch 式抽取：每个 batch 单次构造 system/user，调用一次 LLM。
- 构造 messages：[`stage2_task_abstraction.py#L120`](../src/stages/stage2_task_abstraction.py#L120)
- `task_memory`：[`MemoryManager.get_task_memory`](../src/core/memory_manager.py#L61)

#### Stage 3：维护“训练 messages trace”，但调用输入 messages 每步重建

- LLM 决策 action 的 messages：每次在 [`Stage3TrajectoryGeneration._get_task_action`](../src/stages/stage3_trajectory_generation.py#L322) 里重新 build。
- 训练 messages trace：在 [`Stage3TrajectoryGeneration._generate_trajectory`](../src/stages/stage3_trajectory_generation.py#L114) 内累积 append。

最终写入 trajectory 文件：
- 保存：[`DataStorage.save_trajectory`](../src/data/storage.py#L205)
- trajectory 内包含 `messages` 字段（Stage3 构造 `Trajectory(...)` 时传入）：[`stage3_trajectory_generation.py#L238`](../src/stages/stage3_trajectory_generation.py#L238)

### 3.3 跨阶段：messages 如何“延续”？

production 链路的主线设计是：
- Stage1/2 不做对话延续（每次都是 system+user 一次性输入）。
- Stage3 把“训练 messages trace”持久化到 trajectory JSON。
- Query Rewrite 进一步消费 trajectory 里的 `messages` 作为上下文：
  - [`QueryRewriter._generate_variants`](../src/stages/query_rewrite.py#L122)

因此，跨阶段延续的不是“LLM 对话上下文”，而是结构化产物：
- triplets（Stage1 输出）
- tasks（Stage2 输出）
- trajectories + messages trace（Stage3 输出）

---

## 4. 你要快速定位的 3 个切入点（建议阅读顺序）

1. APIClient 怎么把 messages 发出去 + 重试：[`src/core/api_client.py`](../src/core/api_client.py#L96)
2. Stage1/2 的 system/user prompt 如何拼：[`src/prompts/exploration.py`](../src/prompts/exploration.py#L12) / [`src/prompts/task_abstraction.py`](../src/prompts/task_abstraction.py#L13)
3. Stage3 如何“既调用 LLM 又累积 messages trace”：[`src/stages/stage3_trajectory_generation.py`](../src/stages/stage3_trajectory_generation.py#L114)

---

## 5. 与 legacy 链路的关键差异（便于对照）

- production 的 task_generate 使用 OpenAI 风格 dict messages（`{"role": ..., "content": ...}`），不使用 LangChain `SystemMessage/HumanMessage/AIMessage`。
- production 的 retry 不会修改 messages；legacy 的 retry 常见会在同一 messages 列表上 append（对话式“续写”）。
- production 把“训练 messages trace”作为数据产物落盘（trajectory JSON），而不是把对话历史作为 agent 长期 state。
