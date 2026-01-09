# WebArena：`task.validate()` 与 reward 计算（BrowserGym 视角）

本文作为 [webarena/docs/task_loading_flow.md](task_loading_flow.md) 的补充，专门把 **reward 产出** 与 **`task.validate()` 调用链** 讲清楚：

- reward 从哪里来？每一步都会算吗？什么时候 episode 结束（terminated）？
- WebArena 的 reward（score）到底依赖什么（`intent` / `eval` / `answer`）？
- `task.validate()` 与 Chat（`chat_messages`）是怎么交互的？

> 讨论范围：BrowserGym 的 `BrowserEnv` + BrowserGym 的 `GenericWebArenaTask`（安装在 venv 的 site-packages 内）。

---

## 1. 总览：reward/validate 在 `BrowserEnv.step()` 里发生

从 BrowserGym 的角度，reward 不是 “agent 自己写出来的”，而是 **环境在 `step()` 的后半段（`post_step()`）调用任务的 `validate()` 计算出来的**：

- `BrowserEnv.step(action)`：执行 action（Python code / function call）后立刻进入 `post_step()`：[browsergym/core/env.py#L432-L466](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L432-L466)
- `BrowserEnv.post_step(info, validate=True)`：等待页面稳定、做安全检查、然后触发 `_task_validate()` 来拿到 `(reward, done, user_message, task_info)`：[browsergym/core/env.py#L467-L538](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L467-L538)
- `_task_validate()`：实际调用 `self.task.validate(self.page, self.chat.messages)`，并做一个“validate 期间页面被改坏”的恢复：[browsergym/core/env.py#L540-L555](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L540-L555)

BrowserGym 对 reward 的抽象契约在 `AbstractBrowserTask.validate()` 的 docstring：

- reward 是“since last call to validate()” 的增量概念；done 表示任务是否结束（成功或失败都算结束）：[browsergym/core/task.py#L30-L60](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/task.py#L30-L60)

---

## 2. `BrowserEnv.step()` 的细节：action 执行失败也会进入 validate

`BrowserEnv.step()` 大致分两段：

1) **执行 action**（可能抛异常）

- 通过 `action_mapping` 把 agent 的输出转换成可执行代码（如果配置了 mapping）：[browsergym/core/env.py#L446-L458](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L446-L458)
- 执行失败会记录 `self.last_action_error`，并尝试解析 `TimeoutError` 写入 `info["action_exec_timeout"]`：[browsergym/core/env.py#L460-L465](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L460-L465)

2) **统一收尾**：无论 action 成功与否，都会 `return self.post_step(info)`：[browsergym/core/env.py#L465](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L465)

这意味着：

- reward/terminated 的决定，主要由 `post_step()` → `task.validate()` 来做。
- action 报错并不必然终止 episode；是否终止取决于任务 validate 的 `done` 或环境配置（例如 infeasible）。

---

## 3. `BrowserEnv.post_step()`：为什么要“等页面稳定”再 validate

`post_step()` 在 validate 之前做了几个关键操作（这些细节决定了 reward/validate 的时机与可重复性）：

1) **等待一小段时间**（让 JS 回调有机会把 active page 设置好），并用 `self.context.cookies()` 触发 Playwright 回调（注释里称为 hack）：[browsergym/core/env.py#L486-L491](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L486-L491)

2) **等待 DOM/network idle**（`_wait_dom_loaded()`）：[browsergym/core/env.py#L492-L494](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L492-L494)

3) 若 `validate=True`：

- 做 `_active_page_check()`（因为 action 可能打开/切换 tab）：[browsergym/core/env.py#L499-L503](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L499-L503)
- 可能阻塞等待用户消息（用于 human-in-the-loop/演示交互）：[browsergym/core/env.py#L505-L507](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L505-L507)
- 最终调用 `_task_validate()` 拿到 reward/done/user_message/task_info：[browsergym/core/env.py#L509-L513](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L509-L513)

4) 统一写入 observation 与终止信号：

- 若 task 给了 `user_message`，会被加入 chat 作为 role=`user`：[browsergym/core/env.py#L523-L527](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L523-L527)
- `terminated` 的判定：`done` 或者（开启 `terminate_on_infeasible` 且收到 infeasible 消息）：[browsergym/core/env.py#L533-L536](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L533-L536)

> 结论：**reward 的计算时点不是“action 执行完立刻”，而是 “页面稳定 +（可选）用户交互 + task.validate 完成”之后。**

---

## 4. `_task_validate()`：为什么要“恢复页面/历史”

`_task_validate()` 在调用 `task.validate()` 前会保存：

- `prev_active_page = self.page`
- `prev_page_history = self.page_history.copy()`

然后调用 `self.task.validate(self.page, self.chat.messages)`。[browsergym/core/env.py#L540-L546](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L540-L546)

之后如果检测到 validate 期间改变了 active page 或 page history，就会回滚恢复：[browsergym/core/env.py#L547-L555](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/env.py#L547-L555)

含义：

- BrowserGym 默认假设：**`validate()` 不应破坏环境的页面状态**（否则会影响后续 observation 与动作执行）。
- 但为了兼容一些任务实现（例如 evaluator 内部可能访问页面信息），这里做了兜底恢复。

---

## 5. WebArena 的 `GenericWebArenaTask.validate()`：reward 怎么算、done 何时结束

WebArena 在 BrowserGym 侧的任务实现是 `GenericWebArenaTask`。

### 5.1 validate 的输入：`page` 与 `chat_messages`

`BrowserEnv` 传给任务的是：

- 当前 active 的 Playwright `page`
- chat 消息列表 `self.chat.messages`

chat 的数据结构是形如 `{role, timestamp, message}` 的 dict，`add_message()` 会把 `assistant/infeasible/user` 等写进去：[browsergym/core/chat.py#L55-L66](../../myenv/webarena/lib/python3.10/site-packages/browsergym/core/chat.py#L55-L66)

### 5.2 WebArena validate 的“安全闸”：禁止跳出 WebArena 站点

在评测前，WebArena 会遍历所有打开的 tab（`page.context.pages`），检查其 netloc 是否在允许列表里；如果出现未授权域名，直接：

- reward=0
- done=True
- info 里返回 error

见 [browsergym/webarena/task.py#L159-L168](../../myenv/webarena/lib/python3.10/site-packages/browsergym/webarena/task.py#L159-L168)

这也是 reward/validate 的一个关键点：**validate 不只是“算分”，也承担了策略约束与失败终止。**

### 5.3 WebArena validate 如何从 chat 里提取 “answer”

WebArena 的 evaluator 只需要最终答案（通常来自 STOP）。BrowserGym 的实现用了一个简化规则：

- 如果最后一条 chat 消息的 role 是 `assistant`：把它当作 STOP 的 `answer`
- 如果最后一条是 `infeasible`：把 STOP 的 `answer` 设为 `N/A`
- 否则用 `ActionTypes.NONE`，并用一个占位 answer 规避 evaluator 内部的一个 fuzzy-match bug

见 [browsergym/webarena/task.py#L172-L181](../../myenv/webarena/lib/python3.10/site-packages/browsergym/webarena/task.py#L172-L181)

> 这解释了一个现象：**很多时候 reward 只在 agent“说出最终答案/STOP”之后才会变成 >0**。

### 5.4 WebArena reward 的本质：`score = evaluator(...)`

WebArena 任务在 `setup()` 阶段构建 evaluator（`self.evaluator = evaluator_router(self.config_file)`），而 `validate()` 每次调用 evaluator 得到 `score`：[browsergym/webarena/task.py#L185-L199](../../myenv/webarena/lib/python3.10/site-packages/browsergym/webarena/task.py#L185-L199)

done 的逻辑：

- 如果 `score > 0` 或者 `last_action["action_type"] == STOP`：done=True
- 否则 done=False

见 [browsergym/webarena/task.py#L200-L203](../../myenv/webarena/lib/python3.10/site-packages/browsergym/webarena/task.py#L200-L203)

因此对 WebArena 来说，reward/terminated 的典型形态是：

- **非 STOP 且未答对**：reward=0, done=False（继续探索）
- **STOP**：无论答对与否，done=True（episode 结束；reward 可能是 0 或 >0）
- **答对（score>0）**：done=True（提前结束）

---

## 6. WebArena evaluator 在用什么字段打分（为什么是 `intent` 而不是 `intent_template`）

WebArena 的 evaluator 读取 config json（BrowserGym 在 `setup()` 把当前 config dump 到临时文件），然后主要使用：

- `configs["eval"]["reference_answers"]`
- 以及在 fuzzy match 场景下使用 `configs["intent"]` 作为判别上下文

见 [webarena/evaluation_harness/evaluators.py#L130-L170](../../myenv/webarena/lib/python3.10/site-packages/webarena/evaluation_harness/evaluators.py#L130-L170)

因此：

- 运行时 reward 计算依赖的是 `intent` 与 `eval`（参考答案/打分方式）。
- `intent_template`/`intent_template_id` 是数据集元数据（用于分组/去重/生成），不进入打分核心路径。

---

## 7. 一个可操作的 mental model（理解 reward 稀疏的原因）

你可以把 WebArena 在 BrowserGym 里的 reward 理解为：

- 每一步都在 `post_step()` 触发一次 `validate()`，但 evaluator 实际只关注“最终答案”（STOP 的 answer）。
- 所以在大多数探索步骤里：reward 往往是 0。
- 当 agent 输出最终答案（使最后一条 chat 变成 role=`assistant`），`validate()` 才会把它映射为 STOP-answer 并调用 evaluator 得到可能的正分。

如果你后续要做 reward shaping（更密集的奖励信号），就需要：

- 修改 task 的 `validate()` 让它在中间步骤也能给出非零 reward，或
- 在 env/agent 层引入额外的 reward signals（例如基于 DOM 状态/子目标完成）。

> 本文只解释现有实现，不额外引入新机制。
