# WebArena 奖励信号说明

## 关键代码位置
- 确认奖励写入：`browsergym/experiments/loop.py` 的 `StepInfo.from_step()` 捕获 `reward`，并尝试从 `env_info['RAW_REWARD_GLOBAL']` 取 `raw_reward`。`save_summary_info()` 将两者累加为 `cum_reward`、`cum_raw_reward`。
- 奖励产生：`browsergym/core/env.py` 的 `step() -> post_step() -> _task_validate()`，最终调用任务的 `validate()` 返回 `(reward, done, user_message, info)`。
- WebArena 任务定义：`browsergym/webarena/task.py` 的 `GenericWebArenaTask.validate()` 调用 WebArena 官方评估器 `webarena.evaluation_harness.evaluators.evaluator_router()`，产生评分 `score`。

## step.reward 的来源与流程
1) `env.step(action)` 执行动作
- 通过 `action_mapping` 将高层动作字符串转换为可执行 Python 代码，调用 Playwright 操作页面。

2) `post_step(validate=True)` 触发验证
- 页面加载完成后调用 `_task_validate()`。

3) `_task_validate()` 调用任务的 `validate()`
- 对 WebArena 任务，`GenericWebArenaTask.validate()` 构造“伪轨迹”（只含最后动作答案），调用评估器 `evaluator_router(config_file)`。
- 评估器根据任务类型选用具体实现：
  - `StringEvaluator`：精确匹配 / must-include / fuzzy-match（fuzzy/ua 会调用 `llm_fuzzy_match`、`llm_ua_match`，即通过 LLM 判定相似度）。
  - `URLEvaluator`：URL 规则匹配。
  - `HTMLContentEvaluator`：HTML 内容检查。
  - 其余任务特定 evaluator（如购物、GitLab 等）在 `evaluators.py` 内部动态路由。
- 评估器返回 `score`（通常是 0.0 或 1.0，个别任务可能为 [0,1] 连续值）。

4) 终止判定
- `validate()` 返回 `(score, done, msg, info)`；`post_step` 将 `terminated = done or infeasible_flag`，`truncated=False`。`reward=score` 即 `step.reward`。

5) 汇总
- 每步的 `reward` 累加到 `cum_reward`，写入 `summary_info.json`。

## step.raw_reward 的来源与机制
- `StepInfo.from_step()` 额外尝试读取 `env_info['RAW_REWARD_GLOBAL']`。该字段需环境在 `env.step` 的 `info` 中显式返回。
- WebArena 默认实现（`GenericWebArenaTask.validate`）未返回 `RAW_REWARD_GLOBAL`，所以多数运行中 `raw_reward` 为 `None` 或 `0`，累加时被过滤（`if step.raw_reward`），导致 `cum_raw_reward` 常见为 0。
- 设计目的：给支持“未裁剪/未归一化”奖励的环境预留通道，便于诊断或自定义奖励 shaping。

## 两者的区别
- `reward`（cum_reward）：生效的决策奖励，直接来自任务评估器的 `score`，用于成功判定与训练/评测（本仓库脚本默认以 `cum_reward>0` 判成功）。
- `raw_reward`（cum_raw_reward）：可选的“原始奖励”记录，只有环境在 `info` 提供 `RAW_REWARD_GLOBAL` 时才会累加；默认 WebArena 未提供，因此多为 0 或缺失。

## 是否依赖 LLM
- 动作执行与奖励计算本身不调用 LLM；
- 但某些评估器路径（如 `StringEvaluator.fuzzy_match` / `ua_match`）会调用 `llm_fuzzy_match` 让 LLM 判断答案相似度，这只影响评分阶段，与 agent 的动作生成解耦。

## 常见现象解释
- `cum_reward = 1.0` 但 `cum_raw_reward = 0`：任务成功给了奖励 `1.0`，但环境未返回 `RAW_REWARD_GLOBAL`（或返回 0），被累加时过滤。
- `cum_reward = 0`：评估器未判成功（或提前截断），视为失败/未完成。
