# Demo 模式流程说明（--demo）

本文件说明 `webarena/demo/task_generate/main.py` 的 demo 模式（`--demo`）在做什么、数据流怎么走、以及内置示例 HTML（`DEMO_HTML`）从何而来。

## 1. Demo 模式是什么？

`--demo` 是一种“离线演示/快速自测”模式：
- 不需要提供真实 URL（`--url`）或本地 HTML 文件（`--file`）。
- 程序直接使用 `src/demo_html.py` 中的 `DEMO_HTML` 字符串作为页面输入。
- 后续流程（页面摘要、任务意图生成、验证/答案推断、格式化输出）与正常模式一致。

## 2. 内置示例 HTML（DEMO_HTML）从何而来？

内置示例 HTML **不是从线上抓取**来的，也不是从某个外部数据集自动导入的。

它来源于：
- `webarena/demo/task_generate/src/demo_html.py` 中定义的常量 `DEMO_HTML = """..."""`。

设计目的：
- 构造一个“Magento Admin - Dashboard”风格的简化页面骨架（导航、表格、列表、输入框、按钮等），让生成器在没有真实站点的情况下，也能稳定触发意图生成逻辑。

页面里包含的典型信息块：
- 顶部导航：`Orders / Products / Customers / Reports`
- 指标卡片：`Lifetime Sales`、`Average Order`
- 最近订单表格：`Order ID / Customer / Total / Status`
- 热销产品列表：`Best Selling Products (2023)`
- 客户统计列表
- 搜索区域：文本输入框 + Search 按钮
- 快捷操作按钮：Add New Product / Create Order / View All Reports

这份 HTML 的定位是“演示用 stub（桩数据）”，用于验证管线能跑通，不代表真实 WebArena 环境页面。

## 3. demo 模式完整流程（从命令行到落盘）

下面按执行顺序解释 `main.py` 在 `--demo` 情况下做了什么。

### 3.1 参数解析：`parse_args()`

- `--demo` 与 `--url`、`--file` 互斥，且必须三选一：
  - `input_group = parser.add_mutually_exclusive_group(required=True)`
- demo 模式只需要：
  - `python main.py --demo`

### 3.2 构建配置：`build_config(args)`

- 生成 `Config`：包含三部分
  - `APIConfig`: `api_type`、`openai_api_key`、`model_name`
  - `WebArenaConfig`: `sites`、`base_url`（默认 `--start-url`）
  - `GenerationConfig`: `num_intents`、`min_confidence`、`output_dir`

注意：
- demo 模式的 HTML 输入固定，但 `--site`、`--start-url` 仍会写入最终任务 JSON 中（影响 `sites`、`start_url` 字段）。

### 3.3 获取 HTML：`get_html_content(args)`

当 `args.demo == True` 时：
- 打印：`[INFO] 使用内置示例 HTML (演示模式)`
- 返回：`DEMO_HTML`

这一步是 demo 模式的关键差异点：
- 不会读文件
- 不会发起网络请求

### 3.4 执行生成管线：`TaskGenerationPipeline(config).run(...)`

`main()` 中调用：
```python
pipeline = TaskGenerationPipeline(config)
tasks = pipeline.run(
    html_content=html_content,
    num_intents=config.generation.num_intents,
    start_task_id=args.start_id
)
```

这一步内部（简化理解）：
1. 对 HTML 做页面摘要/结构提取（把“页面是什么、有什么可交互元素/信息块”转成更适合 LLM 的输入）。
2. 让 LLM 生成若干条可能的任务意图（intent）。
3. 对每条意图做可执行性校验，并推断评测所需的参考答案（reference_answers）。
4. 过滤掉低置信度任务（由 `--min-confidence` 控制）。
5. 输出为 WebArena 任务 JSON 列表（每个 task 含 `sites/task_id/start_url/intent/eval/...`）。

### 3.5 保存输出：`tasks.json` + `conversation_history.json`

当 `tasks` 非空时，`main()` 会：
- 按配置决定是否创建时间戳子目录：
  - 默认：`generated_task/YYYYMMDD_HHMMSS/`
- 写入两份文件：
  - `tasks.json`
  - `conversation_history.json`（记录 LLM 调用 `messages` 与解析后的 JSON 响应，用于追溯/调试）

补充说明（对话历史格式）：
- `messages` 按 OpenAI chat 规范保存，为一组 `{role, content}`，role 仅包含：`system` / `user` / `assistant`。
- `response` 会从 assistant 的 `content` 中提取并解析 JSON，落盘为结构化 JSON（而不是原始字符串）。

## 4. 如何运行 demo 模式

最小命令：
```bash
python main.py --demo
```

常用调参：
```bash
python main.py --demo --num-intents 10 --min-confidence 0.8 --output-dir ./generated_task
```

如果需要看报错堆栈：
```bash
python main.py --demo --verbose
```

## 5. 常见理解误区

- `--demo` 不是“访问 WebArena demo 站点”。它只是用内置 HTML 走一遍生成管线。
- 生成任务的 `start_url` 仍来自 `--start-url` 参数（默认值已写死为 shopping_admin 管理后台地址）。
- demo HTML 中出现的文字（例如订单、销量）只是示例内容，不保证与任何真实站点一致。
