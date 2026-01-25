# Experience Demo MVP 计划（plan.md）

## 目标
在 `webarena/demo/experience_demo` 目录内实现一套**自包含**的 MVP，用于展示“经验（experience）检索”对 WebArena 任务完成率的提升：

- 固定问题（task intent）：`What is the top-1 best-selling brand in Quarter 1 2022`
- 运行两组实验：
  - **Baseline（无经验）**：不注入经验，允许偶尔成功，但统计上更差。
  - **With-Experience（检索 top-3 经验）**：通过 embedding 相似度检索最相关的 3 条人工经验，注入上下文后再跑，期望成功率更高。
- 固定模型：`model_provider=cloudgpt` + `model_name=gpt-4.1-20250414`（实际 LLM 调用只用裸 model name）

## 约束与原则
- **自包含约束（最重要）**：experience_demo 目录之外的仓库代码只能用于“阅读参考”，不能被直接 import/调用；需要在 experience_demo 内实现完整闭环（实验入口、agent、经验检索、trace 产物）。
- 允许“照抄/复刻” [webarena/run.py](../../run.py) 的入口结构与参数风格（作为参考实现并复制到本目录），但复制后应只依赖 experience_demo 内的 agent/检索实现。
- **MVP 优先**：先保证跑通、可复现、可对比，后续再做工程化/优雅化。

## 范围（Scope）
### In-scope
- CLI 入口：支持 `--task_name webarena.1` + `--task_config_path` monkeypatch（复刻 run.py 的行为）。
- agent：最小可用的 BrowserGym Agent（支持多步探索、最终提交答案/STOP）。
- experience 经验库：人工编写（jsonl 或 yaml 均可），至少覆盖 shopping_admin 的 best-seller 报表类任务。
- embedding 检索：使用真实向量模型（开源 embedding 模型优先），实现 top-k 相似度检索（cosine）。
- 注入策略：把 top-3 经验注入 system prompt（或 developer message）+ 明确输出约束（动作格式）。
- trace 落盘：至少包含每步 obs 摘要、检索结果、messages、action、reward/done、最终答案。
- 登录态（storage_state）：使用 demo 私有目录下的 storage_state。本 MVP **不实现 auto-login**。
- 动作空间：固定使用 `bid`。
- 截图：每步保存 screenshot 到 results 目录。

### Out-of-scope（MVP 暂不做）
- 自动从 trace 归纳经验（本阶段用人工经验即可）。
- 大规模数据集生成/评测。
- 完整复刻仓库级 conversation_logger / autoeval（可用更轻量 trace）。

## 固定实验设定
- Task：`webarena.1`
- Intent：`What is the top-1 best-selling brand in Quarter 1 2022`
- 参考答案（string_match）：`Sprite`
- Task 配置来源：默认覆盖为 [webarena/config_files/test.raw.json](../../config_files/test.raw.json)
- Model：`model_provider=cloudgpt` + `model_name=gpt-4.1-20250414`
- 统计对比：baseline / with-experience 各运行 3 次

## 运行前置条件（必须）
### 1) 站点环境变量（固定）
运行前设置以下环境变量：

```bash
BASE_URL="http://166.111.53.249"
export WA_SHOPPING="$BASE_URL:7770/"
export WA_SHOPPING_ADMIN="$BASE_URL:7780/admin"
export WA_REDDIT="$BASE_URL:9999"
export WA_GITLAB="$BASE_URL:8023"
export WA_WIKIPEDIA="$BASE_URL:8888/wikipedia_en_all_maxi_2022-05/A/User:The_other_Kiwix_guy/Landing"
export WA_MAP="$BASE_URL:3000"
export WA_HOMEPAGE="$BASE_URL:4399"
```

### 2) 登录态（storage_state，demo 私有目录）
- 本 demo 使用私有目录落盘（不依赖任务 JSON 里的 `./.auth/...`）。
- 本阶段不做 auto-login：需要你预先准备好 storage_state 文件（建议后续在 demo 内提供“一次性人工登录生成 storage_state”的辅助脚本）。
- 固定路径：`webarena/demo/experience_demo/.auth/shopping_admin_state.json`

## 推荐目录结构（experience_demo 内）
> 下面是目标结构（MVP 允许少量调整），所有逻辑都应在 experience_demo 内。

- `webarena/demo/experience_demo/`
  - `plan/`
    - `plan.md`
    - `task.md`
  - `README.md`（运行说明、环境变量、常见报错）
  - `requirements.txt`（本 demo 额外依赖，比如 sentence-transformers）
  - `run_demo.py`（入口：复刻 run.py 的 CLI 形态与 monkeypatch；替换 agent 实现）
  - `agent/`
    - `agent.py`（BrowserGym Agent + Args）
    - `prompting.py`（system/user prompt 模板与注入点）
    - `actions.py`（动作 schema、解析、失败重试策略）
  - `experience/`
    - `experiences.jsonl`（人工经验库）
    - `schema.md`（经验字段解释与写法规范）
  - `retrieval/`
    - `embedder.py`（开源 embedding 模型封装 + 缓存）
    - `index.py`（建索引/加载索引）
    - `retrieve.py`（top-k cosine 检索）
  - `trace/`
    - `writer.py`（落盘：jsonl + summary）
    - `types.py`（可选：简单 dataclass）
  - `results/`（运行产物根目录；每次运行一个子目录）
  - `.auth/`（demo 私有登录态目录，不提交到版本库）

## 关键设计
### 1) 经验（experience）格式
建议每条经验是一个“可检索文本块 + 元数据”，例：

- `id`: string
- `site`: `shopping_admin`
- `tags`: ["bestsellers", "brand", "period"]
- `query_hint`: 可选（帮助检索命中）
- `summary`: 经验摘要（用于 embedding 检索；短、信息密度高）
- `content`: 经验正文（用于注入 prompt；强约束、可执行、带校验点）

经验正文建议结构：
- **Goal**：重述任务
- **Do**：操作路径（菜单/页面/筛选项）
- **Don’t**：常见误区（brand vs product）
- **Verify**：如何确认 period=Quarter 1 2022、输出只含 brand

### 2) 检索（embedding + topK）
- 使用开源 embedding（sentence-transformers），默认模型：`sentence-transformers/all-MiniLM-L6-v2`。
- embedding 输入：
  - query：使用 intent 原文
  - documents：使用每条经验的 `summary`（不是 `content`）
- 相似度：cosine
- 取 top-3：用于 prompt 注入。
- 缓存：将经验向量缓存到 `experience/embeddings.npy`（或 json），保证复现速度。

### 3) 注入策略
- Baseline：system prompt 不包含任何经验；或仅包含通用规则。
- With-experience：system prompt 追加“Retrieved Experiences (Top-3)”段落，按 score 降序拼接。
  - 注入内容：使用每条经验的 `content`
- 输出约束：
  - 行为动作：用固定 JSON schema（例如 `{"action": "CLICK", ...}` / 或 BrowserGym 支持的动作 DSL）。
  - 最终回答：必须有明确 `FINAL_ANSWER` 或 `STOP` 动作，使 WebArena 环境能判定正确。

### 4) auto-login
本 MVP 不实现 auto-login。登录态由 demo 私有目录下的 storage_state 提供。

### 5) 动作空间（Action Space）
- 固定使用 `bid`（与 [webarena/run.py](../../run.py) 默认一致）。
- prompt 中必须清晰说明如何引用元素 bid，以及如何输出 click/type/scroll 等动作。

### 6) 截图
- 每步保存 screenshot 到 `results/<run_id>/screenshots/`，用于对比展示与复盘。

## 产物与验收标准
### 产物（必须）
- `run_demo.py` 可运行两种模式：baseline / with-experience。
- `experiences.jsonl` 至少包含 6–10 条经验；对本任务能检索到 3 条相关经验。
- `results/<run_id>/summary.json`：包含最终答案、是否等于 Sprite、top-3 经验 id/score。
- `results/<run_id>/trace.jsonl`：逐步记录（step、obs 摘要、action、reward、done、messages 摘要）。

### 验收（MVP）
- 同一 task、同一模型、同一 auth 状态下：
  - baseline：成功率低于 with-experience（允许偶然成功）。
  - with-experience：在有限次数（例如 3 次）内至少成功 2 次，并能在 summary 中看到命中的 top-3 经验。

## 风险与缓解
- 站点环境变量/凭据缺失 → README 明确；运行前检查并给出友好报错。
- 视觉/AXTree/HTML 过大导致 token 爆炸 → obs 摘要与裁剪策略；限制每步注入长度。
- 模型早停/不循指 → system prompt 加强“必须继续直到完成任务”，并在动作解析失败时自动 retry。

## 待确认问题（最多 15 个，后续会随着问答更新）
（已收敛到 0）

---
更新时间：2026-01-21
