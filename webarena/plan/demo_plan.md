
# BestSellers 对比 Demo 计划（无 experience vs 有 experience）

目标：做一个**可复现**的 demo，对比同一个“BestSellers”任务在：

1) **不加载任何 experience**（workflow 长期策略）时，agent 容易被误导并失败；
2) **加载与任务高度相关的 experience**（手工或从 trace 归纳）后，agent 成功完成。

本计划以当前入口 [webarena/run.py](webarena/run.py) 为准；experience 的注入路径使用现成机制：`--workflow_path`（会被拼到 system prompt，见 [webarena/agents/legacy/agent.py](webarena/agents/legacy/agent.py)）。

---

## 术语与产物定义（统一口径）

- **trace**：一次运行产物（位于 `results/.../`），至少包含：
	- `experiment.log`（BrowserGym loop 的文本日志，`induce_rule.py`/`induce_prompt.py` 已能解析）
	- `conversation_history.json`（由 `conversation_logger` 落盘，含每次 LLM call 的 messages；截图会被拆出保存到 `images/`）
	- `summary_info.json`（若存在，用于快速判断 reward/success）
- **experience**：可复用的“长期策略/规则/操作手册”文本片段（workflow memory）。形式上就是一段可直接追加到 system prompt 的文本。
	- 当前代码里，experience 最简单的落地形式：`workflow/*.txt`，由 `--workflow_path` 注入。
- **experience 检索**：根据当前任务的 query/intent/页面信息，用 embedding 语义检索从 experience 库里选出 top-K（建议 K=3）拼成当前 run 的 workflow。

---

## Demo 选择：BestSellers（推荐落在 shopping_admin）

“BestSellers”在 `shopping_admin`（Magento Admin）里通常对应 **Reports / Products / Bestsellers** 这类入口，天然适合演示：

- 误导性任务：把“BestSellers”描述成前台（shopping site）或其它菜单入口，诱导 agent 走错路径。
- experience：告诉 agent 正确的定位路径、常见坑（如先登录、左侧导航、日期范围/筛选等）。

---

## 顶层 To-do List（含执行步骤 + 责任人）

> 标注规则：
> - **[你]**：需要你来决定/执行（例如挑选具体任务文本、验收、录屏）
> - **[Copilot]**：你可以把“可直接复制给 Copilot 的指令”发给我，我能直接改代码/加脚本
> - **[你 + Copilot]**：你提供输入/确认，我负责实现与迭代

### 任务清单 (To-do List)

- [ ] 1) 跑通环境与基线运行
- [ ] 2) 定义任务详情（误导逻辑与判定标准）
- [ ] 3) 确定任务承载方式 (JSON/OpenEnded)
- [ ] 4) 获取 Run A（无经验）失败 Trace
- [ ] 5) 归纳 Experience (自动+人工)
- [ ] 6) 实现 Experience 检索与自动注入
- [ ] 7) 获取 Run B（有经验）成功 Trace 并对比
- [ ] 8) 对 gpt-4o 进行 Prompt 加固

### 1) 跑通环境与基线运行（确保 trace 可落盘）

- **责任人**：[你]
- 具体步骤：
	1. 确保 WebArena 相关服务与 URL 环境变量已就绪（`WA_SHOPPING_ADMIN` 等），参考 [webarena/README.md](webarena/README.md)。
	2. 选择先用更稳的模型：把 `--model_name` 切到 `cloudgpt/gpt-4.1`（或你现有可用的 4.1 名称），先把 pipeline 跑通。
	3. 用 `--headless False` + 合理 `--slow_mo` 便于观察与录屏。
	4. 运行一次任意 `webarena.<id>` 或 `openended`，确认 `results/.../conversation_history.json` 会生成。

### 2) 定义 BestSellers demo 的“误导版任务”和“成功判定”

- **责任人**：[你]
- 具体步骤（建议一次写清楚，避免反复改）：
	1. 决定 demo 网站：建议 `shopping_admin`。
	2. 写 **误导版任务**（intentionally misleading）：
		 - 例如：让 agent 去前台找“Best Sellers”并完成某个动作，但实际应该在 admin 报表里找。
	3. 写 **成功判定**（你要在 demo 里展示什么作为成功）：
		 - 最好是“到达正确页面 + 读取到一个可验证的字段/条目”。
		 - 例如：成功打开 Bestsellers 报表页面，并读出第一名商品名（或截图作为证据）。
	4. 明确起始状态：是否需要登录、账号密码从哪里来（WebArena 通常会在任务说明里提供凭据）。

### 3) 选择任务承载方式：openended vs 自定义 task config JSON

- **责任人**：[你 + Copilot]
- 推荐方案（更可复现）：用 `--task_name webarena.<id>` + `--task_config_path <your_json>` monkeypatch `test.raw.json`。
- 具体步骤：
	1. **[你]** 决定：
		 - A) 用 `openended`（简单，但任务文字/起始 URL 交互可能更依赖运行时输入）
		 - B) 用自定义 JSON（最可控，适合 demo）
	2. **[Copilot]**（若选 B）：我会生成一个 `webarena/demo/bestsellers_demo/tasks_bestsellers.json`，里面只放 1-2 条任务，确保可复现。

### 4) 采集“无 experience”失败 trace（Run A）

- **责任人**：[你]
- 具体步骤：
	1. 不传 `--workflow_path`（或传一个空文件），其余参数保持一致。
	2. 固定 `--task_name`、`--task_config_path`、`--max_steps`、`--model_name`，避免变量太多。
	3. 运行并保存：
		 - `results/.../conversation_history.json`
		 - `results/.../experiment.log`
		 - 录屏（可选，但 demo 很加分）
	4. 记录失败模式：是走错站点？早停？卡在登录？还是解析 action 反复重试？

### 5) 从 trace 归纳 experience（trace -> experience）

- **责任人**：[你 + Copilot]
- 优先用现成归纳脚本：
	- `induce_rule.py`：偏“规则/手工风格”总结
	- `induce_prompt.py`：偏“neural-based”总结（直接调 OpenAI SDK）

#### 5.1 自动归纳（LLM 总结）

- **责任人**：[Copilot]
- 可直接复制给 Copilot 的指令：
	- “新增一个脚本 `webarena/demo/bestsellers_demo/trace_to_experience.py`：输入一个 `results/...` 目录，读取其中的 `conversation_history.json` + `experiment.log`，抽取关键 steps（页面 URL、关键 action、失败原因/修正建议），输出一个 workflow 文本到 `webarena/workflow/experience/bestsellers_v1.txt`。同时给出一个极简模板，便于后续人工改写。”

#### 5.2 人工补强（当自动总结不够好）

- **责任人**：[你]
- 具体步骤：
	1. 在 `webarena/workflow/experience/bestsellers_v1.txt` 手写补充 5-10 条强约束规则（简短、可执行）。
	2. 重点写“导航路径 + 常见误区 + 不要早停”。
	3. 保持风格与现有 `webarena/workflow/*.txt` 一致（“Do/Don’t + 例子”）。

### 6) 构建 experience 库与语义检索（top-3 注入）

- **责任人**：[你 + Copilot]
- 目标：在 Run B 中，不是手动指定某一个 workflow，而是“根据任务自动选出最相关的 3 个 experience 拼接注入”，从而展示“会用经验”。

#### 6.1 经验库的数据结构（最小可行）

- **责任人**：[Copilot]
- 建议结构（MVP）：
	- `webarena/workflow/experience_db/experiences.jsonl`
		- 每行：`{id, site, title, triggers, text_path}`
	- experience 文本：`webarena/workflow/experience_db/text/<id>.txt`

#### 6.2 embedding 与检索实现（两条路线二选一）

- **责任人**：[你 + Copilot]
- 路线 A（更稳定、少依赖）：本地向量模型（SentenceTransformer）
	- Pros：不依赖外部 embedding API
	- Cons：需要加依赖与下载模型
- 路线 B（更省事）：OpenAI/CloudGPT embeddings
	- Pros：实现快、效果通常更好
	- Cons：依赖 key/额度

- 可直接复制给 Copilot 的指令（实现 MVP，默认路线 A）：
	- “在 `webarena/demo/bestsellers_demo/` 下新增：
		1) `build_experience_index.py`：读取 `experience_db/` 下的所有 txt，生成 `index.json`（含 embedding 向量，可用 numpy list 存）
		2) `retrieve_experience.py`：输入 task query + site，返回 topK=3 的 experience 文本拼接结果
		3) `make_workflow_for_task.py`：生成临时 workflow 文件（例如 `webarena/workflow/_tmp/current_workflow.txt`）
	- 约束：不引入大型数据库；先用纯文件 + 余弦相似度即可。”

### 7) 加载 experience 后再跑一次（Run B），并固化“对比素材”

- **责任人**：[你]
- 具体步骤：
	1. Run B 使用与 Run A 完全相同的任务与环境参数，仅新增：
		 - `--workflow_path webarena/workflow/_tmp/current_workflow.txt`
	2. 运行完成后，对齐两次 run 的：
		 - 成功率（是否达到成功判定）
		 - step 数
		 - 是否出现早停
		 - 关键页面是否一致
	3. 输出 demo 资产（建议）：
		 - 两段录屏
		 - 两份 `conversation_history.json`
		 - 一份对比说明（1 页即可）

### 8) 针对 gpt-4o“循指/早停”问题的策略（并行推进）

- **责任人**：[你 + Copilot]

#### 8.1 先切到 gpt-4.1 把链路跑通

- **责任人**：[你]
- 具体步骤：
	1. Run A/Run B 全部用 `gpt-4.1`（或你认为更稳的模型）先拿到稳定 demo。
	2. 记录同样任务下 `gpt-4o` 的失败模式作为对照材料。

#### 8.2 对 gpt-4o 做 prompt 加固（system prompt 增强循指）

- **责任人**：[Copilot]
- 目标：减少“没完成就停 / 省略关键步骤 / 不验证就回答”。
- 可直接复制给 Copilot 的指令：
	- “在 `webarena/agents/legacy/dynamic_prompting.py` 的 `SystemPrompt` 增加一段‘anti-early-stop’内容：
		- 明确要求：未满足任务成功条件不得结束；每一步都要验证页面状态；遇到不确定先探索/搜索/返回；禁止凭空回答。
		- 保持输出格式不变（仍是 `<action>...</action>`）。
		- 提供一个开关（例如 `Flags.strict_following=True`）以便只在 demo 里打开。”

---

## 建议的 Run 命令模板（你跑 demo 时用）

> 注意：这里给的是“模板”，你需要把 `--task_name` / `--task_config_path` / `--model_name` 替换成你最终确定的值。

- Run A（无 experience）：
	- `python webarena/run.py --task_name webarena.<ID> --task_config_path <PATH_TO_JSON> --model_name <MODEL> --headless False --slow_mo 30 --max_steps 50`

- Run B（有 experience，通过检索生成 workflow）：
	1) 先生成临时 workflow（如果实现了检索脚本）：
		 - `python webarena/demo/bestsellers_demo/make_workflow_for_task.py --task "..." --site shopping_admin --topk 3 --out webarena/workflow/_tmp/current_workflow.txt`
	2) 再运行：
		 - `python webarena/run.py --task_name webarena.<ID> --task_config_path <PATH_TO_JSON> --workflow_path webarena/workflow/_tmp/current_workflow.txt --model_name <MODEL> --headless False --slow_mo 30 --max_steps 50`

---

## 验收标准（建议写死，避免 demo 争议）

- Run A：在 `max_steps` 内未达到成功判定（或明显走错站点/页面），并能在录屏/日志中复现“被误导”。
- Run B：在 `max_steps` 内达到成功判定；对比 Run A，关键差异来自 experience（workflow 注入）而不是其它参数变化。

---

## 需要你先给我的 3 个最小信息（我后续才能把脚本/JSON 做到完全贴合）

1) “BestSellers”你指的是哪个站点/页面？（建议 `shopping_admin`；如果你想 demo 在 `shopping` 前台也可以）
2) 成功判定你希望展示什么？（打开页面即可 / 读出 top1 商品名 / 导出报表等）
3) 你准备用哪个模型名当 `gpt-4.1`？（确保 `--model_name` 可用）

