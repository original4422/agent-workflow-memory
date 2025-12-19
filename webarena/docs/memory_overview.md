# WebArena 代理记忆（memory）机制说明

## 组成与分类
- **即时记忆（memory tag）**：由代理在每一步生成的 `<memory>` 内容，记录当前步骤后的关键信息，存入 `GenericAgent.memories` 列表。其收集与展示逻辑在 [webarena/agents/legacy/dynamic_prompting.py](webarena/agents/legacy/dynamic_prompting.py) 的 `Memory`、`History`、`MainPrompt` 组件中，开关由 `Flags.use_memory` 控制。
- **思考链（think tag）**：与记忆类似的 `<think>`，用于链式推理，存入 `GenericAgent.thoughts`，同样受 `Flags.use_thinking` 控制。
- **历史回放（history）**：当 `Flags.use_history` 为真时，`History` 会串联前序观测、动作、记忆，形成多步上下文（可选附带差分、错误日志、动作历史等）。
- **Workflow 记忆（长期指令）**：通过 `Flags.workflow_path` 指定的文件内容，直接追加到系统提示（system prompt），作为固定的操作指南/策略，不随步骤更新。示例文件位于 [webarena/workflow/](webarena/workflow/)。

## 运行时记忆使用流程
1. **接收观测**：环境提供观测后，`GenericAgent.get_action` 记录到 `obs_history`（见 [webarena/agents/legacy/agent.py](webarena/agents/legacy/agent.py)）。
2. **构建提示**：`MainPrompt` 根据当前观测与 `flags` 选择性拼装：
   - 当前观测（HTML/AXTree/截图/错误）。
   - 历史（若开启 `use_history`，可含动作、记忆、diff、错误日志）。
   - 动作空间描述。
   - 可选 `<think>` 与 `<memory>` 填写区。
   - 若 `workflow_path` 存在，则把对应文件内容直接附加到系统提示中（持久策略）。
3. **模型响应解析**：模型返回的文本经 HTML 标签解析器提取 `<action>`、`<memory>`、`<think>`；若缺失或格式错误会触发重试。
4. **记忆存储与循环**：提取到的 `<memory>` 存入 `self.memories`，在后续步骤的 `History` 和 `Memory` 区块中再次呈现，为模型提供跨步上下文。

## Workflow 记忆的来源与使用差异
- **来源**：workflow 记忆文件由用户或脚本生成。仓库提供的生成管线在 [webarena/README.md](webarena/README.md) 中说明：
  1) 运行任务收集轨迹；2) 通过 `autoeval` 评估；3) 用 `induce_rule.py` 或 `induce_prompt.py` 将高分轨迹归纳为 workflow 文本（存放在 `workflow/` 目录）。
- **组织方式**：Workflow 记忆是独立文件的长程策略，不随步骤变化；即时记忆则是模型逐步产出的短程笔记，按步骤保存在内存列表。
- **使用时机**：
  - Workflow 记忆：在每次提示构建时自动注入系统提示，影响全局决策，适合“固定操作手册/规则”。
  - 即时记忆：在每步模型输出时生成，随后在历史中循环提示，适合“临时缓存状态/计划”。
- **区分点**：Workflow 记忆不依赖 `use_memory` 开关，只要提供 `workflow_path` 就会生效；即时记忆需 `Flags.use_memory=True` 才会在提示与历史中出现。

## 关键开关与建议
- `Flags.use_memory`：开启逐步 `<memory>` 生成与回放（默认在 [webarena/run.py](webarena/run.py) 中为 False）。
- `Flags.use_history` / `use_action_history` / `use_diff` / `use_error_logs`：决定历史信息的丰富度，影响提示长度与令牌消耗。
- `Flags.workflow_path`：指定 workflow 文件路径即可启用长期策略，无需修改模型输出格式。
- 模型需输出合法的 `<action>`（及可选 `<think>`、`<memory>`）标签，否则解析重试会增加时延与成本。

## 一目了然
- 短期记忆：模型逐步写入 `<memory>`，跨步回放，需显式开启 `use_memory`。
- 长期策略：外部 workflow 文件，始终注入 system prompt，不随步骤变化。
- 二者互补：workflow 负责共性操作准则；即时记忆记录当前任务的局部状态与计划。