# WebArena Task Generator (CuES-Lite)

> 基于 CuES (Curiosity-driven and Environment-grounded Synthesis) 方法的轻量级实现，自动生成符合 WebArena 格式的 Task 数据。

## 📖 项目简介

本项目是 [CuES](https://arxiv.org/abs/2512.01311) 论文方法在 WebArena 场景下的简化实现。CuES 是一个好奇心驱动、环境接地的数据合成框架，用于生成高质量的 Agentic RL 训练数据。

### 核心思想

CuES 的核心流程包括：
1. **Curious Exploration** - 好奇心驱动的环境探索
2. **Task Abstraction** - 从轨迹中抽象任务
3. **Quality Control** - 质量验证和过滤

本项目将上述流程简化为一个线性 Pipeline，适用于从静态 HTML 页面生成 WebArena 任务。

## 🔄 核心流程图解

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         CuES-Lite Pipeline                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐  │
│   │   HTML   │────▶│  Generator   │────▶│  Annotator   │────▶│ Formatter │  │
│   │  Input   │     │  (Intent)    │     │  (Answer)    │     │  (JSON)   │  │
│   └──────────┘     └──────────────┘     └──────────────┘     └──────────┘  │
│        │                  │                    │                   │        │
│        ▼                  ▼                    ▼                   ▼        │
│   ┌──────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────┐  │
│   │  Page    │     │   Intent     │     │  Validation  │     │ WebArena │  │
│   │ Summary  │     │   List       │     │  + Answers   │     │   JSON   │  │
│   └──────────┘     └──────────────┘     └──────────────┘     └──────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 详细数据流

```
HTML Input (URL/文件)
    │
    ▼
┌─────────────────────────────────┐
│ HTMLProcessor.summarize_page() │  ← 提取页面标题、文本内容、交互元素
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ IntentGenerator.generate()     │  ← LLM 根据页面信息生成任务意图
│ (对应 CuES Stage 2)            │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ AnswerAnnotator.validate()     │  ← LLM 验证可执行性并推断答案
│ (对应 CuES Stage 3)            │
└─────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────┐
│ TaskFormatter.format_tasks()   │  ← 封装为 WebArena JSON 格式
└─────────────────────────────────┘
    │
    ▼
generated_tasks.json (Output)
```

## 📋 字段映射说明

下表说明 CuES 概念如何映射到 WebArena 任务格式：

| CuES 概念 | 本项目实现 | WebArena JSON 字段 |
|-----------|-----------|-------------------|
| Environment State | `HTMLProcessor.summarize_page()` | (输入，非输出) |
| Task Query | `IntentGenerator.generate()` | `intent` |
| Task Description | 与 Query 合并 | `intent` |
| Validation Result | `AnswerAnnotator.validate_and_solve()` | `eval.reference_answers` |
| Confidence Score | `confidence` 字段 | (用于过滤，不输出) |
| Action Sequence | 简化省略 | (WebArena 不需要) |

### WebArena JSON 输出示例

```json
{
  "sites": ["shopping_admin"],
  "task_id": 0,
  "require_login": true,
  "storage_state": "./.auth/shopping_admin_state.json",
  "start_url": "http://166.111.53.249:7780/admin",
  "intent": "What are the top-3 best-selling products in January 2023?",
  "eval": {
    "eval_types": ["string_match"],
    "reference_answers": {
      "must_include": ["Impulse Duffle", "Overnight Duffle"]
    },
    "reference_url": "",
    "program_html": [],
    "string_note": ""
  }
}
```

### 字段详解

| 字段 | 来源 | 说明 |
|------|------|------|
| `sites` | 配置文件 | 目标网站列表 |
| `task_id` | 自动生成 | 任务唯一标识 |
| `require_login` | 配置文件 | 是否需要登录 |
| `storage_state` | 配置文件 | 登录状态存储路径 |
| `start_url` | 配置文件 | 任务起始 URL |
| `intent` | LLM 生成 | 任务描述/问题 |
| `eval.eval_types` | LLM 推断 | 评估类型 |
| `eval.reference_answers` | LLM 推断 | 参考答案 |

## 🚀 快速开始

## 🧪 Demo 模式说明

demo 模式（`--demo`）会直接使用 `main.py` 中内置的 `DEMO_HTML` 作为输入，不读取本地文件、也不发起 URL 请求。

- 更详细的数据流与 `DEMO_HTML` 来源说明见: [docs/DEMO_README.md](docs/DEMO_README.md)

### 环境依赖

```bash
# 基础依赖
pip install openai requests

# 如果使用 Azure OpenAI (cloudgpt)
pip install azure-identity azure-identity-broker

# 可选：用于更好的 HTML 解析
pip install beautifulsoup4 lxml
```

### 完整依赖 (requirements.txt)

```
openai>=1.0.0
requests>=2.28.0
azure-identity>=1.12.0
azure-identity-broker>=1.0.0
```

### 配置 API Key

#### 方式 1: 使用 Azure OpenAI (cloudgpt) - 推荐

如果你有 Azure 访问权限，程序会自动使用 `cloudgpt_aoai` 模块进行认证，无需手动配置 API Key。

```bash
# 确保已登录 Azure CLI
az login

# 运行程序
python main.py --demo
```

#### 方式 2: 使用 OpenAI API

```bash
# 设置环境变量
export OPENAI_API_KEY="sk-your-api-key"

# 运行程序
python main.py --demo --api-type openai
```

或通过命令行参数：

```bash
python main.py --demo --api-type openai --api-key "sk-your-api-key"
```

### 运行命令示例

#### 演示模式 (使用内置 HTML)

```bash
python main.py --demo
```

#### 从 URL 生成任务

```bash
python main.py --url "http://166.111.53.249:7780/admin"
```

#### 从本地 HTML 文件生成

```bash
python main.py --file "./sample_page.html"
```

#### 自定义参数

```bash
python main.py --demo \
    --num-intents 10 \
    --min-confidence 0.8 \
    --output-dir "./my_tasks" \
    --site "shopping_admin" \
    --model "gpt-4o-20241120-2"
```

### 命令行参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--url` | - | 目标网页 URL |
| `--file` | - | 本地 HTML 文件路径 |
| `--demo` | - | 使用内置示例 HTML |
| `--num-intents` | 5 | 生成的任务数量 |
| `--min-confidence` | 0.7 | 最低置信度阈值 |
| `--output-dir` | ./generated_task | 输出文件夹路径 (自动创建) |
| `--site` | shopping_admin | 目标网站类型 |
| `--start-url` | http://166.111.53.249:7780/admin | 任务起始 URL |
| `--api-type` | azure | API 类型: azure/openai |
| `--api-key` | - | OpenAI API Key |
| `--model` | gpt-4o | 模型名称 |
| `--start-id` | 0 | 起始任务 ID |
| `--verbose` | False | 显示详细输出 |

### 输出文件说明

生成的任务文件将保存在 `generated_task/` 文件夹的时间戳子文件夹中，每次运行会创建一个新的子文件夹：

```
generated_task/
├── 20260107_143022/
│   ├── tasks.json                      # 生成的任务列表
│   └── conversation_history.json       # 完整的LLM对话历史记录
├── 20260107_150815/
│   ├── tasks.json
│   └── conversation_history.json
└── ...
```

**文件说明：**
- `tasks.json`: 符合WebArena格式的任务数据
- `conversation_history.json`: 包含所有LLM API调用的完整记录，包括：
  - 发送的消息（messages）
  - LLM返回的响应（response）
  - 使用的模型参数（model, temperature, max_tokens）

这样的设计保证了：
1. 每次生成的完整可追溯性
2. 便于调试和复现
3. 方便对比不同生成结果

## 📁 代码结构

```
webarena/demo/task_generate/
├── __init__.py         # 模块导出
├── main.py             # 主入口，命令行接口
├── config.py           # 配置管理
├── generator.py        # 核心生成逻辑 (Pipeline, Generator, Annotator)
├── utils.py            # 工具函数 (JSON, HTML, Prompt)
├── requirements.txt    # 依赖列表
├── README.md           # 本文档
├── CHANGELOG/          # 变更日志
│   └── 2026-01-07.md
└── generated_task/     # 输出文件夹 (运行后自动创建)
    ├── 20260107_143022/
    │   ├── tasks.json
    │   └── conversation_history.json
    └── 20260107_150815/
        ├── tasks.json
        └── conversation_history.json
```

### 模块说明

| 模块 | 功能 | CuES 对应 |
|------|------|----------|
| `config.py` | 配置管理 | `config/config.yaml` |
| `utils.py` | 工具函数 | `prompts/`, `data/storage.py` |
| `generator.py` | 核心 Pipeline | `stages/stage2_*.py`, `stages/stage3_*.py` |
| `main.py` | CLI 入口 | `main.py` |

## 🔧 扩展指南

### 添加新的网站类型

1. 在 `config.py` 中添加配置函数：

```python
def get_my_site_config() -> Config:
    return Config(
        webarena=WebArenaConfig(
            sites=["my_site"],
            base_url="http://example.com",
            require_login=True,
            storage_state="./.auth/my_site_state.json"
        )
    )
```

2. 在 `utils.py` 的 `PromptBuilder` 中添加网站特定的 Prompt 模板。

### 自定义 Intent 生成策略

修改 `generator.py` 中的 `IntentGenerator` 类：

```python
class IntentGenerator:
    def generate(self, html_content: str, num_intents: int = 5):
        # 自定义生成逻辑
        pass
```

### 集成真实浏览器执行

可以扩展 `AnswerAnnotator` 类，使用 Playwright 或 Selenium 进行真实页面交互：

```python
class AnswerAnnotator:
    def validate_with_browser(self, intent: str, url: str):
        # 使用 Playwright 执行任务
        # 获取真实的 reference_answers
        pass
```

## ⚠️ 限制与注意事项

1. **答案准确性**: 由于没有真实浏览器执行，生成的 `reference_answers` 是基于 LLM 推理的，可能需要人工验证。

2. **页面状态**: 本工具假设页面是静态的，不处理动态加载的内容（如 AJAX）。

3. **登录状态**: 如果目标页面需要登录，需要预先准备好 `storage_state` 文件。

4. **置信度过滤**: 低于阈值的任务会被自动过滤，可通过 `--min-confidence` 调整。

## 📚 参考资料

- [CuES Paper](https://arxiv.org/abs/2512.01311) - 原始论文
- [WebArena](https://github.com/web-arena-x/webarena) - WebArena 基准测试
- [AgentEvolver](https://github.com/xxx/AgentEvolver) - CuES 原始代码库

## 📄 License

MIT License
