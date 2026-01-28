# Experience Demo — Architecture Diagrams

This file contains **two Mermaid diagrams**:

1. Component diagram (modules and external dependencies)
2. Runtime sequence diagram (one episode / step loop)

---

## 1) Component diagram (modules)

```mermaid
flowchart LR
  %% Entry
  CLI["run_demo.py<br/>CLI + report writer"]

  %% BrowserGym orchestration
  BG["BrowserGym<br/>ExpArgs / EnvArgs / Agent loop"]

  %% Agent
  AG["ExperienceDemoAgent<br/>agent/agent.py"]
  ACTSET["HighLevelActionSet<br/>action space"]

  %% Prompting + actions
  PROMPT["Prompt Builder<br/>agent/prompting.py"]
  PARSER["Action Parsing/Validation<br/>agent/actions.py"]

  %% Retrieval
  RETRIEVE["Retrieval Orchestrator<br/>agent/agent.py::_ensure_retrieval"]
  INDEX["Experience Index<br/>retrieval/index.py"]
  EMBED["Embedder<br/>retrieval/embedder.py"]
  TOPK["Top-k Retrieval<br/>retrieval/retrieve.py"]
  EXPS[("experiences.jsonl<br/>experience/experiences.jsonl")]
  CACHE[("embedding cache<br/>experience/.cache/*.npy")]

  %% LLM
  LLM["Azure OpenAI Client<br/>cloudgpt_aoai + openai.AzureOpenAI"]

  %% Trace
  TRACE["TraceWriter<br/>trace/writer.py"]
  TYPES["Trace Types<br/>trace/types.py"]
  CONV["ConversationHistoryWriter<br/>trace/conversation_history.py"]

  %% Relationships
  CLI --> BG
  BG --> AG

  AG --> ACTSET
  AG --> PROMPT
  AG --> PARSER
  AG --> LLM

  AG --> RETRIEVE
  RETRIEVE --> INDEX
  RETRIEVE --> TOPK
  TOPK --> EMBED
  INDEX --> EXPS
  INDEX --> EMBED
  INDEX --> CACHE

  AG --> TRACE
  TRACE --> TYPES
  AG --> CONV

  %% External libs
  ST["SentenceTransformers<br/>sentence-transformers"]
  ST --> EMBED

  PW["Playwright<br/>via BrowserGym/WebArena"]
  BG --> PW
```

---

## 2) Runtime sequence diagram (one run)

```mermaid
sequenceDiagram
  autonumber
  participant U as User
  participant CLI as run_demo.py
  participant BG as BrowserGym
  participant ENV as WebArenaEnv
  participant AG as ExperienceDemoAgent
  participant IDX as ExperienceIndex
  participant E as Embedder
  participant L as AzureOpenAI
  participant TR as TraceWriter
  participant CH as ConversationHistory

  U->>CLI: start run
  CLI->>BG: prepare
  CLI->>BG: run
  BG->>AG: make agent

  loop each step
    ENV-->>BG: observation
    BG->>AG: preprocess observation

    alt first step
      AG->>AG: build system prompt
      opt use_experience
        AG->>IDX: build or load index
        IDX->>E: embed summaries
        AG->>E: embed goal
        AG->>AG: retrieve top k
        AG->>TR: log retrieval
      end
    end

    AG->>AG: build user prompt
    AG->>L: chat completion
    L-->>AG: output text
    AG->>CH: append conversation pair

    AG->>AG: extract action
    AG->>AG: validate action
    AG->>TR: log step

    BG-->>ENV: step
  end

  CLI->>CLI: archive outputs and write report
```
