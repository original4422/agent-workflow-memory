# Experience Demo MVP 执行清单（task.md）

> 该文件面向“执行型 agent”。目标是按步骤完成 MVP，并能稳定复现 baseline vs with-experience 对比。
> 约束：除 `webarena/demo/experience_demo` 之外的仓库代码只能参考，不能 import。可以复刻 [webarena/run.py](../../run.py) 的 CLI/monkeypatch 设计，但需替换为本目录自写 agent/检索实现。

## 0. 任务定义（固定不变）
- Task：`webarena.1`
- Intent：`What is the top-1 best-selling brand in Quarter 1 2022`
- 目标答案：`Sprite`
- Model：`model_provider=cloudgpt` + `model_name=gpt-4.1-20250414`
- Task config override：使用 [webarena/config_files/test.raw.json](../../config_files/test.raw.json)

## 1. 初始化目录与依赖
1.1 创建目录结构（如 plan.md 所述）。
- [ ] 新建：`README.md`、`requirements.txt`、`run_demo.py`、`agent/`、`experience/`、`retrieval/`、`trace/`、`results/`。

1.2 选择 embedding 实现（开源）。
- [ ] 在 `requirements.txt` 里加入 `sentence-transformers`（及必要依赖）。
- [ ] 选择默认模型（建议：`sentence-transformers/all-MiniLM-L6-v2`）。

1.3 环境检查（运行前 fail-fast）。
- [ ] 检查必须的站点 URL 环境变量（至少 shopping_admin）。
- [ ] 在 README 提供固定环境变量示例（见 plan.md）。
- [ ] 检查 Playwright 浏览器是否安装；缺失时提示 `python -m playwright install`。

1.4 登录态（storage_state，demo 私有目录）。
- [ ] 约定 demo 私有路径：`webarena/demo/experience_demo/.auth/shopping_admin_state.json`。
- [ ] 运行前检查该文件存在；不存在则给出明确报错与“如何手工生成 storage_state”的指引（本 MVP 不做 auto-login）。

## 2. 经验库（人工）
2.1 定义经验 schema。
- [ ] 在 `experience/schema.md` 写清字段与写法规范。

schema 要求（本 demo 固定）：
- `summary`：用于 embedding 检索（短文本）
- `content`：用于注入 system prompt（完整经验）

2.2 编写经验库。
- [ ] 创建 `experience/experiences.jsonl`。
- [ ] 至少写 6–10 条经验（site=shopping_admin），其中至少 2 条强相关：
  - bestsellers 报表路径
  - brand vs product 的易错点
  - period=Quarter 1 2022 的筛选/校验
  - 最终输出只包含品牌名

2.3 经验质量自检。
- [ ] 每条 `content` 不超过 ~200–300 tokens（避免过长）。
- [ ] 至少 1 条包含“错误示例与纠正”（Don’t + Verify）。

## 3. Embedding + 检索
3.1 实现 embedder。
- [ ] `retrieval/embedder.py`：
  - `embed(texts: list[str]) -> np.ndarray`（batch）
  - 支持磁盘缓存（按经验 id + 模型名）。
  - 默认模型：`sentence-transformers/all-MiniLM-L6-v2`

3.2 实现 index。
- [ ] `retrieval/index.py`：
  - 读取 `experiences.jsonl`
  - 计算/加载 embeddings
  - 保存到 `experience/embeddings.*`（npy/json 均可）

3.3 实现 top-k 检索。
- [ ] `retrieval/retrieve.py`：
  - 输入：query（使用 intent 原文）
  - 文档：使用 `experience.summary` 做 embedding 检索
  - 输出：top_k=3 的 `[{id, score, summary, content}]`
  - 相似度：cosine

3.4 写一个检索自测脚本或最小单元测试。
- [ ] 运行一次检索，确保该 intent 命中 3 条相关经验。

## 4. 动作空间与截图（固定）
4.1 动作空间：`bid`
- [ ] action space 固定为 `bid`。
- [ ] prompt 中必须解释 bid 的含义、如何引用元素、以及 click/type/scroll 等动作输出格式。

4.2 每步截图
- [ ] 每步保存 screenshot 到 `results/<run_id>/screenshots/`。
- [ ] `summary.json` 中记录截图目录路径，便于对比展示。

## 5. Agent（自写，不依赖外部 agent）
5.1 选择 action 表示。
- [ ] 固定使用 `bid` action space，输出格式需与 `bid` action_set 对齐。

5.2 实现 prompt。
- [ ] `agent/prompting.py`：
  - system：角色+规则+必须完成任务
  - user：obs 摘要 + intent + 动作空间说明
  - with-experience：在 system prompt 追加 `Retrieved Experiences (Top-3)`（注入 `experience.content`）

5.3 实现 Agent 主循环接口。
- [ ] `agent/agent.py`：
  - `get_action(obs) -> (action, info)`
  - `info` 里包含：`retrieved_ids/scores`、`final_answer`（若有）
  - 解析失败时 retry（最多 N 次）

5.4 obs 摘要策略。
- [ ] 控制 token：
  - AXTree/HTML 只保留 top-N 行或关键区域
  - 记录 `last_action_error`

5.5 obs 模式可配置（默认 AXTree）。
- [ ] `run_demo.py` 增加 `--obs_mode axtree|html|both`（默认 `axtree`）。

## 6. 实验入口（复刻 run.py 结构）
6.1 复刻 CLI。
- [ ] `run_demo.py` 参数至少包含：
  - `--model_provider`（默认 cloudgpt）
  - `--model_name`（默认 gpt-4.1-20250414；实际 LLM 调用只用裸 model name）
  - `--task_name`（默认 webarena.1）
  - `--task_config_path`（默认 ../../config_files/test.raw.json）
  - `--use_experience`（true/false）
  - `--top_k`（默认 3）
  - `--max_steps`（默认 50）
  - `--headless/--slow_mo`

6.2 复刻 monkeypatch（覆盖 site-packages 的 `webarena/test.raw.json`）。
- [ ] 逻辑可按 [webarena/run.py](../../run.py) 的实现复制，但路径与默认参数改为 demo 目录。

6.3 结果目录。
- [ ] 每次运行写到 `results/<timestamp>_<mode>/`，包含：
  - `summary.json`
  - `trace.jsonl`
  - `retrieval.jsonl`（可选）
  - `screenshots/`（必须）

## 7. 对比运行与验收
7.1 Baseline 运行。
- [ ] 跑 3 次 baseline（允许偶尔成功）。
- [ ] 记录每次最终答案与是否 == Sprite。

7.2 With-experience 运行。
- [ ] 跑 3 次 with-experience。
- [ ] 确认每次 summary 里都记录了 top-3 experience id/score。

7.3 汇总报告。
- [ ] 自动生成 `results/report.md` 或 `results/report.json`：
  - baseline 成功率 vs with-experience 成功率
  - 典型失败案例（brand vs product）
  - 被检索命中的经验（top-3）

## 8. 待确认问题（执行前必须澄清）
（已收敛到 0）

---
更新时间：2026-01-21
