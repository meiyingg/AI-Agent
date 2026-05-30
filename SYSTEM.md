# 商会企业投资顾问 —— 系统说明

> 面向商会会员企业的**多 Agent 智能投资顾问**。一个提问进来，系统**自主研判意图**，
> 再决定"直接答"还是"启动多 Agent 投资决策流程"，并在右侧工作台**实时展示每个 Agent 的原生思考链**（Gemini 式）。

技术栈：LangChain / LangGraph · Tongyi `qwen-max` + `qwq-plus`(推理) · DashScope 向量/重排 · Chroma · BM25 · Tavily · FastAPI(SSE) · Next.js + shadcn

---

## 1. 系统全景

```mermaid
flowchart TB
    subgraph FE ["前端 web/ (Next.js + shadcn, pnpm)"]
        direction LR
        SE["📁 会话列表<br/>历史会话切换"]
        CH["💬 对话<br/>答案逐字流"]
        WT["🛠️ Agent 工作台<br/>实时思考链 + 工具轨迹 + 报告卡"]
    end

    FE <-->|"SSE 流式事件"| API

    subgraph BE ["后端 server/ (FastAPI + SSE)"]
        API["/api/chat · /api/memory · /api/threads/"]
        API --> GRAPH
        subgraph GRAPH ["LangGraph 多 Agent 编排"]
            TRI["意图分诊"] --> GEN["通用助手"]
            TRI --> SUP["Supervisor 调度"]
            SUP --> EXP["专家子 Agent 团队"]
            EXP --> ADV["投资建议"]
        end
        GRAPH -. "短期记忆" .-> CK[("SqliteSaver<br/>按 thread_id")]
        GRAPH -. "长期记忆" .-> PF[("全局企业档案<br/>profile.json")]
        GEN -. "高级RAG" .-> RAG[("Chroma + BM25<br/>+ gte-rerank")]
        EXP -. "联网" .-> TAV["Tavily 实时搜索"]
    end

    GRAPH --> MODELS

    subgraph MODELS ["双模型 (DashScope)"]
        FAST["qwen-max<br/>快: 分诊/路由/结构化"]
        THINK["qwq-plus<br/>推理: 原生思考链 + 工具"]
    end
```

**三层**：前端三栏（会话 / 对话 / 工作台）↔ 后端 FastAPI（SSE 流）↔ LangGraph 多 Agent（接双模型 + 记忆 + RAG + 联网）。

---

## 2. 一次提问的端到端流程

```mermaid
sequenceDiagram
    autonumber
    participant FE as 前端
    participant API as FastAPI
    participant LT as 长期档案
    participant G as LangGraph(+短期记忆)

    FE->>API: POST /api/chat {thread_id, 问题} (SSE)
    API->>LT: ① 读全局企业档案
    API->>G: ② invoke(问题 + 档案, thread_id)
    Note over G: ③ checkpointer 按 thread_id 载入会话历史
    G-->>FE: phase: 意图分诊 (running→done, 判定理由)
    alt 一般问答
        G-->>FE: reasoning 流(💭思考链) + token 流(答案)
    else 投资决策
        G-->>FE: route(派单) → 专家 phase(running)
        G-->>FE: reasoning 流 + tool(入参) + tool_result(可读)
        G-->>FE: phase(done, 专家结论) → ... → final(结构化报告)
    end
    Note over G: ④ checkpointer 存回本轮(短期续上)
    API->>LT: ⑤ 会话结束(可选)自动提炼事实更新档案
```

① / ⑤ = 长期记忆（全局档案，跨会话）；③ / ④ = 短期记忆（本会话历史，按 thread 隔离）。

---

## 3. 多 Agent 编排（LangGraph）

```mermaid
flowchart TD
    START(("START")) --> TRI["🧭 意图分诊 triage<br/>chat_model 分类 + 重置本轮草稿"]
    TRI -->|"一般问答"| GEN["💬 通用助手 general<br/>qwq-plus: 思考链 + 自动选 RAG/联网"]
    TRI -->|"投资决策"| SUP["🧠 Supervisor<br/>chat_model 路由 + 防死循环"]

    subgraph TEAM ["专家子 Agent (qwq-plus, 共享状态)"]
        K["📁 内部知识<br/>高级RAG"]
        R["🌐 行业调研<br/>Tavily 联网"]
        A["📊 量化分析<br/>6类金融工具(模拟)"]
    end

    SUP -->|"派单"| K & R & A
    K & R & A -->|"写入 notes + visited"| SUP
    SUP -->|"调研≥2专家"| ADV["✍️ 投资建议 advisor<br/>chat_model + Pydantic 校验"]

    GEN --> E1(("END · 直接答"))
    ADV --> E2(("END · 报告卡"))
```

**关键设计**：
- **总入口是分诊**，不是所有问题都出报告；简单问题走通用助手直接答。
- **最少调研门槛**（≥2 专家才出建议）+ **最大轮数** 防止"啥都没查就出报告"和死循环。
- **状态分两类**：对话历史 `messages` 跨会话持久；本轮调研草稿 `visited/notes` 每轮 `triage` 时重置（自定义 reducer 支持 `__reset__`）。

---

## 4. 为什么引入"思考模型"（核心改造）

### 4.1 之前不行在哪

之前全程用 `qwen-max`（工具调用模型）。它的毛病不是"展示得不好"，而是**推理根本没被生成**：

```mermaid
flowchart LR
    subgraph OLD ["❌ 之前 qwen-max"]
        O1["决定调工具时<br/>只吐工具调用, 不吐推理"] --> O2["工具返回是原始 JSON"]
        O2 --> O3["工作台只有'执行轨迹'<br/>(调了啥/拿到啥) = 像运维 log"]
    end
```

| | 之前（执行轨迹）| 想要（Gemini 式思考）|
|---|---|---|
| 本质 | 系统调了什么工具、拿到什么 | 模型在"想"什么——"这是投资决策，得先查关税，因为…" |
| 来源 | 编排日志 | 模型自己吐的 reasoning |
| 读感 | 像 log | 像一个人在分析 |

要"思考"，就得让模型**真的产出推理链（chain-of-thought）**。

### 4.2 探针验证：哪个模型行

实测 DashScope 的推理模型，关键看两点——**能流式吐思考链** 且 **能同时调工具**（Agent 必须用工具）：

| 模型 | 原生思考链 reasoning_content | 同时调工具 | 结论 |
|---|---|---|---|
| `qwen-plus` + `enable_thinking` | ✅ 流式 | ❌ 400 报错(incremental_output 冲突) | 不可用 |
| **`qwq-plus`** | ✅ 流式(一次调研 321 块) | ✅ 可以 | **选它** |

### 4.3 方案：双模型架构

不把所有环节都换成 qwq-plus（它"想"得很深、很慢），而是**按职责分工**：

```mermaid
flowchart TD
    Q["用户提问"] --> T["🧭 意图分诊"]
    T -->|一般| G["💬 通用助手"]
    T -->|投资决策| S["🧠 Supervisor 路由"]
    S --> W["🌐📊📁 专家子Agent"]
    W --> ADVN["✍️ 投资建议"]

    T -.使用.-> FAST
    S -.使用.-> FAST
    ADVN -.使用.-> FAST
    G -.使用.-> THINK
    W -.使用.-> THINK

    FAST["qwen-max (快)<br/>分诊/路由/结构化报告<br/>不需要可见思考, 要快/要JSON"]
    THINK["qwq-plus (推理)<br/>通用助手 + 专家子Agent<br/>要展示思考的地方"]
```

- **`qwen-max`（快）**：意图分诊、Supervisor 路由、投资建议结构化输出——这些要快、要稳定 JSON，不需要给用户看思考。
- **`qwq-plus`（推理）**：通用助手 + 三个专家子 Agent——这些是真正"干活"的，把它们的思考链展示出来。

### 4.4 思考链怎么流到界面（Gemini 式）

```mermaid
flowchart LR
    M["qwq-plus 流式输出"] --> C1["additional_kwargs<br/>.reasoning_content<br/>= 思考链"]
    M --> C2["content<br/>= 答案 token"]
    C1 --> E1["emit reasoning 事件"]
    C2 --> E2["emit token 事件"]
    E1 --> SSE["SSE"]
    E2 --> SSE
    SSE --> UI1["右工作台<br/>💭 思考过程 (流式滚动)"]
    SSE --> UI2["左对话<br/>答案逐字打出"]
```

**左答案、右思考**，正是 Gemini 那种体验。代价：qwq-plus 思考深，投资决策完整流程从 ~90s 变为 **3–5 分钟**。

---

## 5. 记忆系统（短期 + 长期）

```mermaid
flowchart TB
    subgraph SHORT ["短期记忆 (会话内)"]
        CK[("SqliteSaver checkpointer<br/>memory.sqlite")]
        CK --> M1["按 thread_id 隔离<br/>同会话记住上文 / 跨会话不串台"]
    end
    subgraph LONG ["长期记忆 (跨会话)"]
        PF[("全局企业档案<br/>profile.json")]
        PF --> M2["企业画像/偏好/关键事实/历史结论<br/>每次注入 通用助手 + 投资建议 提示词"]
        PF --> M3["对话结束可自动提炼新事实并入档案<br/>(默认关, 可开)"]
    end
```

- **短期**：LangGraph checkpointer，按 `thread_id` 存整段对话；左侧"历史会话"点开即续聊。
- **长期**：单一**全局企业档案**（小而总相关的"核心记忆"，直接注入提示词，不走检索）——这是行业里 Letta/MemGPT 的 core memory 做法，和"文档 RAG"是**两套独立的库**。
- 在档案抽屉里可**手动查看/编辑**。

---

## 6. 高级 RAG（内部知识）

```mermaid
flowchart LR
    F["内部文档/会议纪要"] -->|"MD5去重→切分→向量化"| VDB[("Chroma 向量库")]
    Q["问题"] --> H["混合检索<br/>BM25(0.3) + 向量(0.7)"]
    VDB --> H
    H --> RR["gte-rerank 重排 TopK"]
    RR --> LLM["LCEL 生成(防幻觉)"]
```

混合检索补关键词召回、重排降误召回；**MD5 去重只用于内部文件**，联网资讯讲新鲜度、只查不落库。

---

## 7. 流式事件协议（SSE）

后端 `execute_events` 吐结构化事件，前端据此渲染：

| 事件 | 含义 | 渲染到 |
|---|---|---|
| `thread` | 会话 id | 记录，刷新会话列表 |
| `phase` | 步骤 running/done（含 mode、判定理由 detail）| 工作台时间线 |
| `route` | Supervisor 派单决定 | 工作台 |
| `reasoning` | **原生思考链增量** | 工作台 💭 思考过程(流式) |
| `token` | **答案增量** | 左对话(打字机) |
| `tool` / `tool_result` | 工具入参 / 可读返回 | 工作台(可展开) |
| `final` | 结构化投资报告 | 工作台报告卡 + 左对话指针 |
| `done` / `error` | 结束 / 出错 | 收尾 / 提示 |

---

## 8. 目录结构

```
meeting-insight-agent/
├── server/main.py            # FastAPI + SSE 后端
├── web/                      # Next.js + shadcn 前端 (pnpm)
│   ├── app/page.tsx          # 三栏布局 + SSE 事件编排
│   └── components/           # chat-panel / worktable / sessions / memory-sheet
├── src/
│   ├── models/factory.py     # 双模型: chat_model(qwen-max) + reasoning_model(qwq-plus)
│   ├── graph/supervisor.py   # 多Agent编排 + 短期记忆 + 事件流
│   ├── agent/                # react_agent(通用助手) / subagents(专家) / advisor / tools
│   ├── memory/               # profile(长期档案) / threads(会话注册表)
│   ├── rag/                  # 向量库 / 混合检索+重排 / 会议KB
│   └── utils/                # config / stream(emit+可读化) / robust(重试降级)
├── config/settings.yml       # 模型/检索/重排/记忆/多Agent 配置
└── main.py                   # CLI: gen-meetings / ingest / ask / advise / ...
```

---

## 9. 诚实说明

- **量化分析的 6 类金融工具是模拟数据**（确定性随机），用于演示工具编排，不是真实测算。
- **联网资讯**走 Tavily 实时检索、不落库（避免过期）。
- **qwq-plus 推理更慢**：换来可见的思考链，投资决策流程会明显变慢；可在 `settings.yml` 切回部分环节用 `qwen-max` 提速。
- 评测用的小问答集与示例文档是合成的，仅演示流程。
