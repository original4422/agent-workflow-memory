# Experience Demo（Experience Retrieval + Prompt Injection）

该 demo 位于 `webarena/demo/experience_demo/`，目标是用最小闭环展示：

- **Baseline**：不使用经验注入（`--use_experience false`）
- **With-Experience**：对“任务目标(goal)”做 embedding 检索，取 top-k 经验注入 system prompt（`--use_experience true --top_k K`）

对比两种模式在同一 WebArena 任务上的成功率，并产出可复盘的 trace 与实验报告。

## 一句话快速开始（Quickstart）

从仓库根目录运行（推荐）：

```bash
myenv/webarena/bin/pip install -r webarena/demo/experience_demo/requirements.txt
myenv/webarena/bin/python -m playwright install

# baseline
myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience false

# with-experience (top-3)
myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience true --top_k 3

# suite: baseline N runs + with-exp N runs, writes report.md/report.json
myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --suite true --n_runs 3 --top_k 3
```

如果你第一次运行就报错，优先看下方的“运行前置条件（必须）”和“常见问题”。

## Demo 做了什么（原理与流程）

### 1) 经验库（Experience Library）

- 文件：`experience/experiences.jsonl`
- schema：见 `experience/schema.md`

每条经验包含两个关键字段：

- `summary`：短文本，用于 embedding 检索
- `content`：长文本，用于注入 system prompt（可执行的操作步骤 + 易错点 + 校验点）

### 2) Embedding 与检索（Top-k cosine）

- 默认 embedding 模型：`sentence-transformers/all-MiniLM-L6-v2`（可通过 `--embedding_model` 覆盖）
- query：使用任务的 `goal`（即 WebArena intent/目标描述）
- documents：使用每条经验的 `summary`
- 相似度：cosine（实现上等价于对归一化向量做点积）

实现位置：

- `retrieval/embedder.py`：向量化
- `retrieval/index.py`：加载经验 + 构建/加载 embedding cache
- `retrieval/retrieve.py`：top-k 检索

### 3) Prompt 注入（System Prompt Injection）

- Baseline：system prompt 不包含任何检索经验
- With-Experience：将 top-k 经验的 `content` 附加到 system prompt 的“Retrieved Experiences”段落

实现位置：

- `agent/prompting.py`：system/user prompt 模板
- `agent/agent.py`：控制是否检索与注入；动作解析失败会自动 retry

### 4) 运行与对比（BrowserGym Experiments）

入口脚本：`run_demo.py`

- 单次运行：直接在 `results/` 下创建 BrowserGym experiment 目录
- suite 模式：在 `results/<timestamp>_suite_.../` 下运行 baseline/with-exp 各 `n_runs` 次，并写出 `report.md`/`report.json`

## 运行前置条件（必须）

### 1) WebArena 站点 URL 环境变量

示例（见 `plan/plan.md`，你也可以按你的部署修改 `BASE_URL`）：

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

至少需要 `WA_SHOPPING_ADMIN` 对应的站点可访问（本 demo 的检索默认过滤 `site=shopping_admin`）。

### 2) 登录态（Playwright storage_state）

本 demo 不做 auto-login，需要你先准备好：

- `webarena/demo/experience_demo/.auth/shopping_admin_state.json`

#### storage_state 怎么生成？

推荐写一个一次性的本地脚本（有界面模式登录一次，然后保存 storage_state）。示例：

```python
# save_storage_state.py
from playwright.sync_api import sync_playwright


def main() -> None:
		admin_url = "http://localhost:7780/admin"  # change to your WA_SHOPPING_ADMIN
		out_path = "webarena/demo/experience_demo/.auth/shopping_admin_state.json"

		with sync_playwright() as p:
				browser = p.chromium.launch(headless=False)
				context = browser.new_context()
				page = context.new_page()
				page.goto(admin_url)

				# TODO: manually login in the opened browser window
				page.wait_for_timeout(60_000)

				context.storage_state(path=out_path)
				context.close()
				browser.close()


if __name__ == "__main__":
		main()
```

运行：

```bash
myenv/webarena/bin/python save_storage_state.py
```

### 3) CloudGPT / Azure OpenAI 调用凭据

`ExperienceDemoAgent` 使用 `azure.identity.DefaultAzureCredential` 获取 token，并通过 `openai.AzureOpenAI` 调用模型。

常用环境变量：

- `CLOUDGPT_AOAI_ENDPOINT`（默认：`https://cloudgpt-openai.azure-api.net/`）
- `CLOUDGPT_AOAI_API_VERSION`（默认：`2024-06-01`）

`DefaultAzureCredential` 在本地常见的工作方式是：

- 已安装并登录 Azure CLI（例如 `az login`）
- 或者通过环境变量配置服务主体（Service Principal）

如果你不使用 CloudGPT/Azure OpenAI，请改造 `agent/agent.py` 中 `_make_cloudgpt_client()`。

## 运行方式（详细）

### 单次运行

```bash
# default task_name=webarena.1
myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience false

myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py --use_experience true --top_k 3
```

### Suite 对比

```bash
myenv/webarena/bin/python webarena/demo/experience_demo/run_demo.py \
	--suite true \
	--n_runs 3 \
	--top_k 3 \
	--headless true \
	--slow_mo 30
```

### 常用参数（与默认值）

- `--task_name`：默认 `webarena.1`
- `--task_config_path`：默认 `webarena/config_files/test.raw.json`（脚本内部会 monkeypatch 资源读取）
- `--model_provider`：默认 `cloudgpt`
- `--model_name`：默认 `gpt-4.1-20250414`（LLM 调用时只用裸 model name；provider 用于选择 client）
- `--obs_mode`：`axtree|html|both`（默认 `axtree`）
- `--max_steps`：默认 `30`
- `--headless`：默认 `true`
- `--slow_mo`：默认 `30`
- `--use_experience`：默认 `false`
- `--top_k`：默认 `3`
- `--embedding_model`：默认 `sentence-transformers/all-MiniLM-L6-v2`

## 目录结构与产物说明

### 经验与检索缓存

- 经验库：`experience/experiences.jsonl`
- schema：`experience/schema.md`
- embedding 缓存：`experience/.cache/`

缓存机制说明：

- `retrieval/index.py` 会对所有 `summary` 计算 fingerprint
- 当 fingerprint 与 embedding 模型名都没变时，会直接复用 `.cache/` 下的 `.npy` 向量文件
- 想强制重建：删除 `experience/.cache/` 即可

### 实验输出（results）

- `results/`：运行产物根目录
- 每次 run 会生成一个 BrowserGym experiment 目录（含 `summary_info.json` 等）
- suite 模式会额外生成：
	- `report.json`
	- `report.md`

此外，本 demo 还会在每个 experiment 目录下写一个子目录：

- `<exp_dir>/experience_demo/trace.jsonl`：逐步 trace（prompt、llm 输出、action、检索结果等）
- `<exp_dir>/experience_demo/summary.json`：demo 侧的 summary（用于快速定位问题）

## 如何新增/改造经验（实践建议）

1) 按 `experience/schema.md` 增加一条 JSONL（每行一个 JSON）。
2) 优先把“可检索信息”放进 `summary`（短、密度高）；把“可执行流程 + 校验点”写进 `content`。
3) 修改完经验后：

- 要么直接运行（会自动检测 fingerprint 变化并重建）
- 要么删除 `experience/.cache/` 后再运行（最干净）

## 常见问题（FAQ / Troubleshooting）

### 1) 报错：Missing storage_state

说明你没有生成 `webarena/demo/experience_demo/.auth/shopping_admin_state.json`。

- 按上面的 `save_storage_state.py` 方式手工登录生成一次。

### 2) 报错：站点打不开 / 导航到错误地址

通常是 `WA_SHOPPING_ADMIN` 等环境变量没设置或设置错。

- 对照 `plan/plan.md` 的示例导出环境变量。

### 3) 报错：401/403 或无法获取 token

这是 Azure 身份认证链路问题（`DefaultAzureCredential` 没拿到 token）。

- 确认本机已登录 Azure CLI（或改用环境变量方式提供凭据）
- 确认 `CLOUDGPT_AOAI_ENDPOINT` / `CLOUDGPT_AOAI_API_VERSION` 是否正确

### 4) With-experience 没有提升

常见原因：

- 经验库太少/summary 写得不可检索（缺少关键词、过长、信息太泛）
- `content` 没有提供可执行步骤或校验点
- 模型输出经常不符合动作格式，导致重试耗尽

建议：

- 先检查 `<exp_dir>/experience_demo/trace.jsonl` 中 `retrieval` 事件的 top-k 命中是否合理
- 再检查注入的 `prompt_system` 里经验段落是否出现

## 进一步阅读

- `plan/plan.md`：MVP 目标、约束与推荐设定
- `plan/task.md`：执行清单（偏“怎么做”）
