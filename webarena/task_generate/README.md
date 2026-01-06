<h2 align="center">
  🧭 CuES-WebArena: Curiosity-driven Task Generation for WebArena
</h2>

<p align="center">
  基于CuES (Curiosity-driven and Environment-grounded Synthesis) 框架的WebArena任务自动生成工具
</p>

---

## 📖 概述

CuES-WebArena 是一个**好奇心驱动的、环境感知的**框架，用于在WebArena环境中自动合成高质量的代理训练数据，**无需预定义的种子任务**。

本项目基于 [CuES](https://arxiv.org/abs/2512.01311) 论文的方法，针对WebArena网页代理环境进行适配，实现了一个完整的三阶段数据生成管道。

### 核心特性

- **环境感知合成**：任务源自真实的浏览器交互轨迹，确保可执行性
- **好奇心驱动探索**：使用探索记忆树引导新颖动作，减少重复
- **无需种子任务**：可在没有预定义任务的情况下自主探索和生成任务
- **多网站支持**：支持 shopping, shopping_admin, gitlab, reddit, map 等WebArena网站
- **完整管道**：包含探索、任务抽象、轨迹生成三个阶段
- **查询重写**：可选的查询多样化功能，增加训练数据多样性

---

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        CuES-WebArena Pipeline                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Stage 1   │───▶│   Stage 2   │───▶│       Stage 3       │  │
│  │ Exploration │    │   Task      │    │     Trajectory      │  │
│  │  (好奇探索)  │    │ Abstraction │    │    Generation       │  │
│  │             │    │ (任务抽象)   │    │   (轨迹生成)         │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│         │                  │                      │              │
│         ▼                  ▼                      ▼              │
│    triplets.jsonl     tasks.jsonl         trajectories/          │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    Optional: Query Rewrite                │   │
│  │                      (查询重写/多样化)                      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 三阶段流程

#### Stage 1: 好奇心驱动探索 (Curious Exploration)

- **目标**：自主探索WebArena网站，生成交互三元组 (observation, action, next_observation)
- **方法**：使用LLM作为探索代理，结合探索记忆避免重复
- **输出**：`data/triplets/triplets_{session_id}.jsonl`

#### Stage 2: 任务抽象 (Task Abstraction)

- **目标**：从探索轨迹中抽象出具体的、可执行的任务
- **方法**：使用LLM分析交互序列，提取目标导向的任务
- **输出**：`data/tasks/tasks_{session_id}.jsonl`

#### Stage 3: 轨迹生成 (Trajectory Generation)

- **目标**：执行抽象出的任务，生成完整的训练轨迹
- **方法**：使用LLM代理在真实环境中执行任务
- **输出**：`data/trajectories/trajectory_{task_id}.json`

---

## 📁 项目结构

```
task_generate/
├── main.py                     # 主入口程序
├── requirements.txt            # 依赖包列表
├── README.md                   # 本文档
│
├── config/
│   └── config.yaml            # 配置文件
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                  # 核心模块
│   │   ├── __init__.py
│   │   ├── pipeline.py        # 主管道协调器
│   │   ├── api_client.py      # LLM API客户端
│   │   └── memory_manager.py  # 探索记忆管理
│   │
│   ├── data/                  # 数据模型和存储
│   │   ├── __init__.py
│   │   ├── models.py          # Triplet, Task, Trajectory模型
│   │   └── storage.py         # 数据持久化
│   │
│   ├── stages/                # 三个阶段实现
│   │   ├── __init__.py
│   │   ├── stage1_exploration.py          # 好奇探索
│   │   ├── stage2_task_abstraction.py     # 任务抽象
│   │   ├── stage3_trajectory_generation.py # 轨迹生成
│   │   └── query_rewrite.py               # 查询重写
│   │
│   ├── prompts/               # LLM提示词
│   │   ├── __init__.py
│   │   ├── exploration.py     # 探索阶段提示
│   │   ├── task_abstraction.py # 任务抽象提示
│   │   └── trajectory.py      # 轨迹生成提示
│   │
│   └── utils/                 # 工具函数
│       ├── __init__.py
│       └── logger.py          # 日志工具
│
└── data/                      # 生成的数据 (自动创建)
    ├── triplets/              # 探索三元组
    ├── tasks/                 # 抽象任务
    ├── trajectories/          # 执行轨迹
    │   └── failed/            # 失败的任务
    ├── sessions/              # 会话信息
    ├── memories/              # 探索记忆
    └── rewrites/              # 重写的查询
```

---

## 🚀 快速开始

### 1. 环境准备

```bash
# 进入项目目录
cd task_generate

# 创建虚拟环境 (推荐)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 安装 Playwright 浏览器
playwright install chromium
```

### 2. 配置

编辑 `config/config.yaml`:

```yaml
# API配置 - 设置你的API密钥
api:
  api_key: "your-api-key-here"  # 或设置环境变量 OPENAI_API_KEY
  model_name: "openai/gpt-4o"   # 支持: openai/gpt-4o, azure/gpt-4o, glm/glm-4.6

# 环境配置
environment:
  website: "shopping_admin"     # 要探索的网站
  headless: false               # 是否无头模式运行浏览器

# 阶段配置
stage1:
  rollout_num: 3               # 探索轮数
  max_steps: 20                # 每轮最大步数

stage2:
  min_confidence: 0.6          # 最小任务置信度

stage3:
  max_steps: 25                # 每个任务最大步数
```

### 3. 运行

```bash
# 运行完整的三阶段管道
python main.py --stage all

# 只运行探索阶段
python main.py --stage stage1

# 只运行任务抽象 (需要先有triplets)
python main.py --stage stage2

# 只运行轨迹生成 (需要先有tasks)
python main.py --stage stage3

# 带查询重写
python main.py --stage all --rewrite

# 指定探索需求
python main.py --stage stage1 --requirement "focus on product management features"

# 提取概念集后再探索
python main.py --stage all --extract-concepts
```

---

## 📋 命令行参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--config` | str | config/config.yaml | 配置文件路径 |
| `--stage` | str | all | 运行阶段: all, stage1, stage2, stage3 |
| `--session-name` | str | auto | 会话名称 |
| `--input-file` | str | auto | 输入文件 (stage2/stage3) |
| `--website` | str | config | 网站类型: shopping, shopping_admin, gitlab, reddit, map |
| `--task-name` | str | None | 特定的WebArena任务名称 |
| `--headless` | flag | False | 无头模式运行 |
| `--requirement` | str | None | 探索需求说明 |
| `--extract-concepts` | flag | False | 探索前提取概念集 |
| `--rewrite` | flag | False | 启用查询重写 |
| `--verbose` | flag | False | 详细日志输出 |

---

## 📊 输出数据格式

### Triplet (三元组)

```json
{
  "triplet_id": "abc123",
  "env_id": "rollout_0_xyz",
  "observation": "当前页面的AXTree或HTML",
  "action": "click(\"product-link\")",
  "next_observation": "动作后的页面状态",
  "url": "http://...",
  "reward": 0.0,
  "done": false,
  "step_number": 5,
  "timestamp": "2025-01-05T10:30:00"
}
```

### Task (任务)

```json
{
  "task_id": "task_001",
  "description": "在商品管理页面添加一个新产品",
  "query": "How do I add a new product to the catalog?",
  "action_sequence": [
    "click(\"products-menu\")",
    "click(\"add-product\")",
    "fill(\"product-name\", \"New Product\")",
    "click(\"save-button\")"
  ],
  "ground_truth": "产品成功添加到目录",
  "confidence": 0.85,
  "difficulty": "medium",
  "website": "shopping_admin"
}
```

### Trajectory (轨迹)

```json
{
  "trajectory_id": "traj_001",
  "task_id": "task_001",
  "query": "How do I add a new product?",
  "description": "添加新产品到目录",
  "steps": [
    {
      "step_number": 0,
      "observation": "...",
      "action": "click(\"products-menu\")",
      "next_observation": "...",
      "reward": 0.1
    }
  ],
  "success": true,
  "final_reward": 1.0,
  "total_steps": 4,
  "messages": [
    {"role": "system", "content": "..."},
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}
```

---

## 🔧 高级配置

### 使用 Azure OpenAI

```yaml
api:
  api_key: "your-azure-api-key"
  model_name: "azure/gpt-4o"
  azure_endpoint: "https://your-resource.openai.azure.com/"
  api_version: "2024-02-15-preview"
```

### 使用国内模型

```yaml
# 智谱GLM
api:
  api_key: "your-glm-api-key"
  model_name: "glm/glm-4.6"

# Moonshot Kimi
api:
  api_key: "your-kimi-api-key"
  model_name: "kimi/moonshot-v1-8k"
```

### 自定义探索策略

```yaml
stage1:
  rollout_num: 5          # 增加探索轮数
  max_steps: 30           # 增加每轮步数
  use_memory: true        # 使用探索记忆
  memory_update_freq: 5   # 记忆更新频率
```

---

## 📈 最佳实践

### 1. 探索策略

- 使用 `--requirement` 指定探索重点区域
- 使用 `--extract-concepts` 提取概念集指导探索
- 适当增加 `rollout_num` 获取更多样的交互

### 2. 任务质量

- 调高 `min_confidence` 过滤低质量任务
- 增加 `min_action_length` 确保任务足够复杂
- 检查生成的任务，手动过滤不合理的

### 3. 轨迹生成

- 在 GUI 模式下（非 headless）可以观察代理行为
- 检查 `failed/` 目录分析失败原因
- 使用 `--rewrite` 增加数据多样性

---

## 🐛 故障排除

### 常见问题

**1. 浏览器启动失败**
```bash
# 确保已安装 Playwright 浏览器
playwright install chromium
```

**2. API 调用失败**
```bash
# 检查 API 密钥是否正确设置
export OPENAI_API_KEY="your-key"
```

**3. WebArena 连接失败**
```
# 确保 WebArena 服务正在运行
# 检查 config.yaml 中的 URL 是否正确
```

**4. 内存不足**
```yaml
# 减少并发数
threading:
  max_workers: 2
  enabled: true
```

---

## 📚 相关资源

- [CuES 论文](https://arxiv.org/abs/2512.01311)
- [WebArena 项目](https://webarena.dev/)
- [BrowserGym 文档](https://github.com/ServiceNow/BrowserGym)

---

## 📄 引用

如果您使用本项目，请考虑引用原始 CuES 论文：

```bibtex
@misc{mai2025cues,
  title         = {CuES: A Curiosity-driven and Environment-grounded Synthesis Framework for Agentic RL},
  author        = {Mai, Shinji and Zhai, Yunpeng and Chen, Ziqian and Chen, Cheng and Zou, Anni and Tao, Shuchang and Liu, Zhaoyang and Ding, Bolin},
  year          = {2025},
  eprint        = {2512.01311},
  archivePrefix = {arXiv},
  primaryClass  = {cs.AI}
}
```

---

## 📝 License

MIT License
