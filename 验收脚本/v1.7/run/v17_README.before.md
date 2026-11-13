# ai学习 · AI Agent 语料深度剖析

> 目录：`~/Desktop/study/ai学习/`。写于 2026-10-28。
> 所有结论都指向**这份目录里真实存在的代码**，路径相对 `ai学习/`，格式 `文件:行号`。行号是我当天读到的；上游仓库在更新，按关键字搜比按行号跳更稳。查不到的地方标了【待补】，没有编。
> **本文第 6 章里 `my_ui.py` 的行号一律按当前版本对齐**（v1.6，**1,205 行**）——它是"代码现状"文档。`迭代记录.md` 与 `agent功能手册.html` 的**每一节保留当时那一版**的行号，两边不一致时以本 README 为准去跳代码。
> 图的语法是 Mermaid（Markdown 预览即渲染）；每张图后面都跟了等价的中文说明，只看文字也不丢信息。

---

## 1 全局：一条 Agent 业务链路，四份代码，一个外壳

### 1.1 分层链路图

```mermaid
flowchart TB
    subgraph L5["⑤ 交付外壳 · 你自己写的"]
        APP["我的Agent.app<br/>启动器 + Chrome app 窗口"]
        STOP["关闭Agent.command<br/>关停脚本"]
    end
    subgraph L4["④ 产品与运营层"]
        DIFY["dify<br/>低代码 LLM 应用平台<br/>DSL + 知识库 + 可观测"]
    end
    subgraph L3["③ 企业应用接入层"]
        LC4J["langchain4j<br/>Java 侧的模型 / RAG / 工具抽象"]
    end
    subgraph L2["② 编排内核层"]
        SMOL["smolagents<br/>ReAct 循环 + 代码执行器<br/>你已在此跑通 8 项动作空间"]
    end
    subgraph L1["① 工具与协议层"]
        MCP["modelcontextprotocol/servers<br/>工具即独立进程，JSON-RPC 自描述"]
    end
    LLM["模型侧<br/>百炼 qwen-plus（OpenAI 兼容端点）<br/>只做决策，不执行任何东西"]
    APP --> SMOL
    SMOL --> LLM
    SMOL -->|"本地真执行"| MCP
    LC4J --> LLM
    DIFY --> LLM
    DIFY -.->|"插件 / 工具"| MCP
    SMOL -.->|"尚未接，可接"| MCP
    STOP --> APP
```

一句话读法：**模型只负责"想"，四份代码分别负责"怎么想（smolagents）""用 Java 怎么接（langchain4j）""不懂代码的人怎么把它做成产品（dify）""工具怎么标准化（MCP servers）""怎么让别人双击就能用（你的 App 外壳）"。**

### 1.2 四仓归属表

| 仓库 | 体量 | 版本 / 来源 | 在链路里的节点 | 本机能不能跑 |
|---|---|---|---|---|
| `smolagents/` | 263 MB | `1.27.0.dev0`，git HEAD `96f33fa`(2026-10-06)，**editable 装在 `.venv`** | ② 编排内核 | **能**，已跑通（`my_ui.py` + 桌面 App） |
| `langchain4j/` | 56 MB | `1.23.0-beta33-SNAPSHOT`，tar 解出、无 `.git` | ③ Java 接入层 | 源码可读；编译需 `jdk17`+`mvn39`（已装在 `~/tools`，见 3.8） |
| `dify/` | 166 MB | tar 解出、无 `.git`；`api` 60 MB + `web` 83 MB | ④ 平台层 | **未部署**：`docker/.env` 不存在，`SECRET_KEY=` 空 |
| `servers/` | 5.8 MB | git HEAD `ef9808f`(2026-10-24) | ① 工具/协议层 | **未安装**：无 `node_modules`，且要求 Node ≥ 24（本机 v22.20.0） |

### 1.3 本机实际拓扑（谁在哪个端口上）

```mermaid
flowchart LR
    subgraph HOST["你这台 Intel Mac"]
        subgraph TERM["Terminal.app（唯一有 ~/Desktop 读权限的宿主）"]
            PY[".venv/bin/python my_ui.py<br/>127.0.0.1:7860"]
            LOG["ai学习/.agent-ui.log"]
        end
        GR["OpsUI(GradioUI)<br/>自建 Blocks · my_ui.py:1135<br/>会话库 History · my_ui.py:382<br/>审批门 · my_ui.py:546"]
        DB[("smolagents/.agent-history.sqlite3<br/>sessions · messages · memory")]
        CH["Chrome app 实例<br/>--app=http://127.0.0.1:7860<br/>--user-data-dir=AgentClient"]
        CLOUD["dashscope.aliyuncs.com/compatible-mode/v1<br/>qwen-plus"]
        PY --> GR
        GR -->|"显示层 messages＋模型层 memory 各自覆盖写"| DB
        PY -->|"tee"| LOG
        CH -->|"HTTP，仅回环"| GR
        PY -->|"HTTPS，带你的 Key"| CLOUD
    end
```

要点三条，都不是设计上的浪漫选择，是被系统约束逼出来的：

1. **服务只绑 `127.0.0.1`、`share=False`**（`smolagents/my_ui.py:1198-1201`，v1.1 前在 `:70-72`）。框架默认是 `share: bool = True`（`smolagents/src/smolagents/gradio_ui.py:422`）——照默认调用会把带着你百炼 Key 的 agent 变成 `gradio.live` 公网链接。
2. **冷启动必须让 Terminal 动手**：macOS 的 TCC 不允许"由 `.app` 直接拉起的进程"读取 `~/Desktop` 下已存在文件的内容，`.venv/bin/python` 由 `.app` 直接起会 EPERM 起不来（原因记在 `我的Agent.app/Contents/MacOS/launcher:4-7`）。副作用：每次冷启动多一扇日志终端窗口。
3. **窗口用独立 Chrome profile**（`~/Library/Application Support/AgentClient`），所以你日常 Chrome 的标签页、扩展、登录态完全不参与，也不会被接管。

### 1.4 建议的阅读顺序

1. 你自己那 3 个 Python 文件（第 6 章）——最短路径看清"一个 agent 由哪几块拼成"。
2. `smolagents` 内核（第 2 章）——唯一一份你已经在跑的代码，值得读到行号级。
3. `servers`（第 5 章）——把"工具"从函数升级成协议，概念量最小、收益最大。
4. `langchain4j`（第 3 章）——回你的主栈，看同一套抽象在 Java 里怎么落（`AiServices` 的动态代理值得精读）。
5. `dify`（第 4 章）——平台层，看工程性部分（多租户、DSL、可观测、异步 worker）而不是算法。

---

## 2 smolagents —— 编排内核，"用代码当动作空间"

### 2.1 功能定位

让 LLM 用"写 Python 代码"的方式思考和行动的**最小 Agent 循环引擎**（官方口号 "Agents that think in code!"）。它不是什么都管的框架：核心循环一千行左右，可整份读完。

### 2.2 解决了什么问题

| 对手 | 它的问题 | smolagents 的回答 |
|---|---|---|
| LangChain 式重编排 | 抽象层太多，查一个 bug 要穿七层代理 | 一个 `MultiStepAgent` 基类 + 两个子类，循环骨架一屏看完（`agents.py:540-611`） |
| 原生 function calling | 每步只能吐一个 JSON 调用，多步组合靠模型反复往返，token 浪费且做不了中间计算 | `CodeAgent` 一步 = 一段程序，里面可以循环、判断、串多个工具（`agents.py:1505`、`agents.py:1715-1719`） |
| 通用"agent 平台" | 看不见链路，出问题只能猜 | 每一步是 `TaskStep` 对象，`agent.memory.steps` 可逐条打印（`my_agent.py:78-82` 就是这么自查的） |

### 2.3 模块地图

```mermaid
classDiagram
    class MultiStepAgent {
        +run() agents.py:436
        +_run_stream() agents.py:540
        +_step_stream() 抽象
        +memory
        +tools
        +max_steps
    }
    class ToolCallingAgent {
        +原生 tool-calling agents.py:1215
        +execute_tool_call 白名单 agents.py:1453
        +多线程并行工具 agents.py:1426
    }
    class CodeAgent {
        +输出 code 块 agents.py:1505
        +create_python_executor agents.py:1598
    }
    class Tool {
        +name description inputs
        +forward() tools.py:98
    }
    class toolDecorator {
        +签名与 docstring 反射成 schema tools.py:1061
    }
    class PythonExecutor {
        +send_tools send_variables call
    }
    class LocalPythonExecutor {
        +自研 AST 解释器
        +import 白名单 local_python_executor.py:372
        +final_answer 打桩 local_python_executor.py:1572
    }
    class RemoteExecutors {
        +E2B Docker Modal Blaxel
        +remote_executors.py:53
    }
    class Models {
        +generate() 统一 ChatMessage models.py:452
        +MODEL_REGISTRY models.py:2070
    }
    class AgentMemory {
        +TaskStep ActionStep PlanningStep memory.py:214
        +to_messages 回灌 memory.py:92
    }
    class GradioUI {
        +只是消费 run(stream) gradio_ui.py:279
        +launch 默认 share=True gradio_ui.py:422
    }
    MultiStepAgent <|-- ToolCallingAgent
    MultiStepAgent <|-- CodeAgent
    MultiStepAgent o-- Tool
    Tool <|.. toolDecorator
    CodeAgent --> PythonExecutor
    PythonExecutor <|-- LocalPythonExecutor
    PythonExecutor <|-- RemoteExecutors
    MultiStepAgent --> Models
    MultiStepAgent --> AgentMemory
    GradioUI --> MultiStepAgent
```

**Agent 即工具**：`_setup_managed_agents`（`agents.py:369-387`）给子 agent 填上 `name/description/inputs/output_type`，于是子 agent 本身就是一个 Tool 塞进父 agent 的工具表——多 agent 复用单 agent 的全部机制，**没有第二套路由代码**。所谓 "handover" 只是提示词约定（system prompt 里列出子 agent 名字），不是运行时特性。

### 2.4 一个 step 的真实链路（序列图）

```mermaid
sequenceDiagram
    autonumber
    participant U as 你（或 GradioUI）
    participant AG as Agent 主循环
    participant MEM as AgentMemory
    participant MD as qwen-plus 云端
    participant EX as 本地执行器
    participant TL as 工具函数
    U->>AG: run(task)
    AG->>MEM: 建 TaskStep 写入记忆
    loop 未交卷 且 step_number 不超过 max_steps（agents.py:545）
        AG->>AG: write_memory_to_messages 组装提示，含工具签名
        AG->>MD: generate(messages, stop_sequences, tools_to_call_from)
        MD-->>AG: 决策：工具调用 / 代码块 / final_answer
        AG->>AG: 解析（CodeAgent 抽 code 块，agents.py:1708）
        AG->>EX: 执行
        EX->>TL: 本地真跑，云端不碰你的机器
        TL-->>EX: 返回值
        EX-->>AG: Observation（print 输出 + 最后表达式）
        AG->>MEM: 写 ActionStep，含 error 分支
        Note over AG,MEM: 出错不抛给你，而是回灌成下一步输入<br/>memory.py:138-148 的 "Now let's retry..."
    end
    AG-->>U: FinalAnswerStep
    Note over AG: 超步数走 _handle_max_steps_reached agents.py:625<br/>强制"基于已有记忆总结交卷"，末步标 AgentMaxStepsError :630
```

这条链路里最值得记住的一点：**云端只产生文本，所有副作用都在你机器上执行**——这也是"能不能让 agent 直接读我自己那个面板 URL"是数据出域问题、而不是技术难题的原因。

### 2.5 状态机

```mermaid
stateDiagram-v2
    [*] --> 已收题: TaskStep 入 memory
    已收题 --> 规划中: 开启 planning
    规划中 --> 思考中
    已收题 --> 思考中: 默认路径
    思考中 --> 执行中: 模型给出工具调用或代码块
    思考中 --> 交卷: final_answer
    思考中 --> 报错回灌: 解析失败或生成错误
    执行中 --> 观察回灌: 拿到 Observation
    执行中 --> 报错回灌: 工具越界或沙箱拒绝
    报错回灌 --> 思考中: error 写进 ActionStep 后继续
    观察回灌 --> 交卷: 判定这是 final_answer（agents.py:582-592）
    观察回灌 --> 思考中: 未到 max_steps，继续循环
    观察回灌 --> 熔断: 已到 max_steps（agents.py:545）
    熔断 --> [*]: 强制总结，答案不可信
    交卷 --> [*]
```

### 2.6 难点与采用的手段

| 难点 | 具体表现 | 实际手段（代码位置） |
|---|---|---|
| 代码动作空间的**安全边界** | 模型写的 Python 在你机器上跑，等于把 shell 交给它 | 自研 AST 解释器逐节点求值（`local_python_executor.py:1583`），不走真 `eval`：import 白名单树 `:372`/`:1309`（拒绝文案 `:1317`）、未注册函数禁调 `:859`、builtins 受限 `:906-908`、dunder 调用白名单 `:910-917`、模块属性递归裁剪 `get_safe_module:1271`、超时 `:285` + 操作计数防死循环 |
| 本地沙箱**不是**真沙箱 | 框架自己在注释里承认不可信代码要换后端（`local_python_executor.py:1692-1693`） | `create_python_executor`（`agents.py:1598-1618`）按 `executor_type` 分发 local / e2b / docker / modal / blaxel；`PythonExecutor` 抽象只有 3 个方法（`local_python_executor.py:1677-1685`），远端只是多包一层生命周期（`remote_executors.py:53`） |
| 工具签名怎么让模型看懂 | 模型必须知道参数名、类型、必填 | `Tool.to_code_prompt`（`tools.py:258`）把工具渲染成"函数定义 + docstring"塞进 system prompt；远端执行时用 `get_tools_definition_code`（`tools.py:1335`）生成真实 `import` 代码注入沙箱 |
| 模型**不守规矩** | 吐出不存在的工具名、把 JSON 当字符串、不给闭合标签 | 白名单校验直接拒（`agents.py:1467`：`Unknown tool xxx, should be one of: ...`）；文本里正则抽 tool_calls（`models.py:583`）；参数是字符串就 `parse_json_if_needed`（`agents.py:1334`）；闭合标签缺失就手动补（`agents.py:1693-1695`）；`final_answer = x` 误赋值被正则改写（`local_python_executor.py:332`） |
| 怎么"跳出"深层循环交卷 | 代码可能嵌在函数第 5 层里 | `final_answer` 注册时只是普通工具（`agents.py:402` `setdefault`），本地执行被打桩成抛 `FinalAnswerException`，它继承 `BaseException`——**防被用户代码里的 `except Exception` 吞掉**（`local_python_executor.py:1572-1578`） |
| token 成本看不见 | 排障时不知道上下文涨在哪 | `Monitor.update_metrics`（`monitoring.py:100-117`）打印的是**本次 run 的全生命周期累计**（`run()` 开头 `monitor.reset()`，`agents.py:480`）；**单步真实值**在 `ActionStep.token_usage`（`agents.py:1323`、`agents.py:1697`），网页那行读的是后者。两个口径混用会得出错误结论 |
| 流式体验 | 长思考期间界面空白 | `stream_outputs=True` 时 `_run_stream` 变生成器逐段 yield，模型层吐 `ChatMessageStreamDelta`，用 rich `Live` 边生成边刷（`agents.py:1665-1673`） |
| agent 复用与分享 | 调好的 agent 想存档 / 上线 | `save` / `push_to_hub` / `from_folder`（`agents.py:892`/`1160`/`1118`），反序列化走 `AGENT_REGISTRY` 白名单（`agents.py:1810`）防任意类实例化 |

### 2.7 亮点（这份代码里最值得偷师的四招）

1. **一步 = 一个程序**：动作空间从"选一个工具"升级为"写一段代码"，变量在 executor 的 `state` 里跨步存活（`send_variables`/`send_tools`，`agents.py:490-492`）。
2. **用控制流异常实现交卷**：一个 `BaseException` 子类把答案从沙箱最深处直接抛到主循环——简单、可靠、不怕用户代码捕获。
3. **子 agent 即工具**：多 agent 拓扑不引入新概念，编排能力全部复用单 agent。
4. **防御性补丁密度**：`fix_final_answer_code`、闭合标签回填、Observation 截断（`truncate_content`）——真实世界的 agent 有一半代码在处理"模型不听话"。

### 2.8 边界

它管**循环、工具、执行、记忆、序列化**，不管：RAG 索引（只做检索工具，不做索引管线）、会话持久化（`memory` 纯内存，落盘靠手工 `save`）、工作流可视化 / 低代码 DAG、模型网关与限流计费（LiteLLM 只是可选适配器）。定位是"嵌进更大系统的那颗芯"，不是对外发布的成品。

---

## 3 langchain4j —— 你的主栈上，同一件事的 Java 写法

### 3.1 功能定位

JVM 生态里"把 LLM / RAG / 工具调用接进 Java 应用"的惯用库。README 自陈目标是 *simplify integrating LLMs into Java applications*，并强调它**不是** LangChain-Python 的移植（`langchain4j/README.md:19`、`:38-43`）。

### 3.2 解决了什么问题

20+ 模型供应商、30+ 向量库的 API 各家不同；在企业里换一家模型供应商约等于改一遍业务代码。langchain4j 把差异吸进 provider 模块，业务侧只依赖 `langchain4j-core` 的接口。

**为什么你的组合里必须有它**：smolagents 让你看懂 agent 内核，但生产落地点在 Spring/Quarkus；这一份是"明天就能带进工作"的那一半。两份代码的抽象（Tool / Memory / Agent）正好互相印证。

### 3.3 模块地图与依赖方向

```mermaid
flowchart BT
    CORE["langchain4j-core<br/>只有接口：ChatModel / StreamingChatModel<br/>EmbeddingModel / ChatMemory<br/>ToolSpecification / RetrievalAugmentor"]
    P1["provider 模块（顶层平铺）<br/>langchain4j-open-ai / anthropic / ollama<br/>bedrock / vertex-ai …"]
    S1["embedding-stores 各实现"]
    D1["document-loaders / document-parsers<br/>document-transformers"]
    AGG["聚合模块 langchain4j<br/>AiServices · EasyRAG · splitter"]
    AGENT["langchain4j-agentic<br/>AgenticServices：supervisor / planner"]
    APP["你的业务代码<br/>只写一个 interface"]
    CORE --> P1
    CORE --> S1
    CORE --> D1
    P1 --> AGG
    S1 --> AGG
    D1 --> AGG
    AGG --> AGENT
    AGG --> APP
    AGENT --> APP
```

一个和直觉不一样的点：**没有 `model-providers/` 这个目录**，provider 就是仓库根下平铺的顶层模块。根 `pom.xml:7` 版本 `1.23.0-beta33-SNAPSHOT`。core 关键接口：`ChatModel.java:34`、`StreamingChatModel.java:41`、`EmbeddingModel.java:39`、`ChatMemory.java:21`、`ToolSpecification.java:19`、`RetrievalAugmentor.java:20`、`ChatMemoryStore`（持久化 SPI）。

### 3.4 AiServices 的运行时魔法（序列图）

"一个 Java 接口 = 一个会调工具的 agent"，代码里只有一处魔法：JDK 动态代理。

```mermaid
sequenceDiagram
    autonumber
    participant B as 业务代码
    participant AS as AiServices builder<br/>AiServices.java:194 / :218
    participant PX as Proxy.newProxyInstance<br/>DefaultAiServices.java:205-208
    participant TS as ToolSpecifications<br/>toolSpecificationsFrom :99
    participant CM as ChatModel（provider 实现）
    participant TE as DefaultToolExecutor :134
    B->>AS: 传入 interface + 带 @Tool 的实例 + ChatModel + ChatMemory
    AS->>TS: 反射生成工具规范（Java 类型转 JSON Schema，JsonSchemaElementUtils:40）
    AS->>PX: newProxyInstance(接口, InvocationHandler)
    B->>PX: 像调普通方法一样调用
    PX->>CM: 组装 SystemMessage + 记忆 + 工具规范，发请求
    CM-->>PX: 返回 tool call 或文本
    PX->>TE: 反射调用你的 @Tool 方法
    TE-->>PX: 返回值
    PX->>CM: 结果回灌，内部继续下一轮
    PX-->>B: 一个 String 或 POJO（结构化输出）
```

**`@MemoryId`**（`core/.../MemoryId.java:19`）让同一个 agent 实例按参数值分会话记忆——多用户场景不用自己搭 map。

### 3.5 RAG 管线（活动图）

```mermaid
flowchart LR
    A["文档源 PDF/Office/网页"] --> B["loader<br/>document-loaders"]
    B --> C["parser<br/>apache-tika 等"]
    C --> D["splitter<br/>DocumentSplitters / recursive"]
    D --> E["EmbeddingModel 向量化"]
    E --> F["EmbeddingStore 入库"]
    G["用户提问"] --> H["QueryTransformer 改写"]
    H --> I["QueryRouter 路由到多个库"]
    I --> J["检索 + ContentAggregator 重排去重"]
    F -.-> J
    J --> K["ContentInjector 塞进提示"]
    K --> L["ChatModel 生成"]
    L --> M["答案 + 引用"]
```

入口 `DefaultRetrievalAugmentor.augment()`（`langchain4j-core/.../rag/DefaultRetrievalAugmentor.java:169`），四个阶段组件在同文件 `:125-128`。**每个方框都可替换**——这是它和 dify「知识库黑盒」最大的区别：这里你能亲手换掉重排策略。

### 3.6 难点与手段

| 难点 | 实际手段 |
|---|---|
| 反射密集，GraalVM 原生镜像不友好 | 兼容工作放在外部 `quarkus-langchain4j` 扩展里做，本仓库只保证接口稳定 |
| 一个接口 N 家实现，能力不齐（流式 / 工具 / 视觉 / 结构化） | core 用 `Capability` 枚举显式声明能力，业务侧可探测后降级 |
| Java 类型 → JSON Schema（泛型、嵌套 record、可选性） | `internal/JsonSchemaElementUtils.java:40` 集中处理 |
| 上下文窗口与记忆膨胀 | `ChatMemory`（`:21`）+ 窗口/条数驱逐策略，持久化走 `ChatMemoryStore` SPI |
| 供应商鉴权 / 超时 / 重试差异 | provider 各自实现 `ChatModel`（范式见 `langchain4j-open-ai/.../OpenAiChatModel.java:55`），HTTP 客户端也抽成独立模块 `http-clients/` |

### 3.7 亮点

1. **接口即 SDK**：不写继承、不写装配，一个 interface + `@Tool`/`@SystemMessage`/`@MemoryId` 就长出 agent。
2. **策略全链路可换**：`retrievalAugmentor` / `tools` / `toolProvider` 均可 builder 注入（`AiServices.java:419`、`:537` 附近）。
3. **`langchain4j-agentic`**：`AgenticServices` 提供 supervisor / planner 显式编排，正好补上"smolagents 那种自动循环"与"我想要的可控图"之间的中间档。

### 3.8 本机实际状态（当场查过，纠正一条过期结论）

- 默认 `java -version` 落到 **JDK 8**（1.8.0_201，`/Library/Internet Plug-Ins/...`），但 `~/tools/jdk-17.0.20.1+1/Contents/Home/bin/java` 是 **17.0.20.1**，`~/tools/apache-maven-3.9.16/bin/mvn` 也在；`~/.zshrc:111` 有 `jdk17()`、`:113` 有 `mvn39()`。
  → **能编译**，前提是每条命令前先 `jdk17`（parent pom 要求 `<java.version>17</java.version>`，`langchain4j-parent/pom.xml:39`）。
- `langchain4j-core/target/classes` 里有 **648 个 class 文件**（tar 包自带的 CI 产物），说明这份快照本身构建过；`~/.m2` 无 `dev.langchain4j` 缓存。
- 仓库里**没有 examples 目录**（官方示例在独立的 `langchain4j-examples` 仓库，`README.md:64-70`）。本地最省事的入手点是 `langchain4j-easy-rag`（一行 API 完成摄取 + 检索）。
- 建议首次编译：`mvn39 -pl langchain4j-core -am -o compile`（先离线，避免拉全量依赖）。【待补：本机首次联网编译的实际耗时与失败点】

## 4 dify —— 不是框架，是"把 LLM 应用做成资产"的平台

### 4.1 功能定位与本质差别

框架给你库和抽象，**Dify 给你一个产品**：带持久化、多租户权限、分发（API Key / 内嵌 WebApp）、可观测的完整运行时。你写的东西是 YAML DSL 和配置，不是代码。它解决的问题是"不会写代码的人如何把提示词 / 知识库 / 工作流沉淀成可发布、可监控、可迭代的资产"。

### 4.2 组件与部署视图（这份代码的真实构成）

```mermaid
flowchart TB
    subgraph FE["web · Next.js（83 MB）"]
        ST["Studio 编排界面"]
        WA["内嵌 WebApp"]
    end
    subgraph BE["api · Flask（60 MB）"]
        CTRL["controllers<br/>console 管理端 / service_api 对外端 / inner_api"]
        SVC["services 业务编排"]
        CORE2["core 引擎层<br/>app · workflow · rag · model_manager<br/>plugin · agent · ops"]
        MOD["models · SQLAlchemy 持久化"]
    end
    WD["worker / worker_beat<br/>Celery 异步任务"]
    PD["plugin_daemon（外部 Go 仓库）<br/>模型 / 工具 / provider 全靠它插件化"]
    SB["sandbox + local_sandbox<br/>代码执行节点依赖"]
    AG["新增 agent_backend<br/>dify-agent（Python，基于 Pydantic AI）<br/>dify-agent-runtime（Go，shellctl + Landlock 内核级沙箱）"]
    DB[("Postgres")]
    RD[("Redis 队列")]
    VDB[("向量库，默认 weaviate")]
    NG["nginx :80 / :443"]
    ST --> NG
    WA --> NG
    NG --> CTRL
    CTRL --> SVC --> CORE2 --> MOD --> DB
    CORE2 --> PD
    CORE2 --> SB
    CORE2 --> AG
    SVC --> RD
    RD --> WD
    WD --> DB
    CORE2 --> VDB
```

`docker/docker-compose.yaml` 里 `services:` 共 **47 个**，但只有 **13 个常驻**（`api, web, worker, worker_beat, redis, nginx, plugin_daemon, sandbox, local_sandbox, agent_backend, agent_ssrf_proxy, ssrf_proxy, init_permissions`），其余 34 个用 `profiles:` 门控（数据库二选一、20 多种向量库、knowledge_fs 系列）。默认拉起哪几个由 `docker/.env.example:303` 决定：`COMPOSE_PROFILES=${VECTOR_STORE:-weaviate},${DB_TYPE:-postgresql},collaboration` → 实际约 **16 个容器**常驻，对外只开 nginx 的 80/443（`docker-compose.yaml:980`）。

### 4.3 一次 chatflow 请求的调用链（序列图）

```mermaid
sequenceDiagram
    autonumber
    participant CL as 调用方（WebApp 或 API Key）
    participant CT as ChatApi.post<br/>controllers/service_api/app/completion.py:336
    participant GS as AppGenerateService
    participant GEN as advanced_chat/app_generator.py:75
    participant WE as WorkflowEntry<br/>core/workflow/workflow_entry.py:119
    participant EN as graphon Engine（外部库 0.8.0，api/pyproject.toml:49）
    participant NF as node_factory.py:124-133 扫描注册
    participant VP as VariablePool
    CL->>CT: POST（api key + query + conversation_id）
    CT->>GS: 生成入口
    GS->>GEN: 起线程 / 队列
    GEN->>WE: 构造 WorkflowEntry
    WE->>NF: 按 DSL 里的节点类型取实现类（惰性映射 :266）
    WE->>EN: run() :208，产出 EngineEvent 流
    loop 每个节点
        EN->>VP: 写输出变量
        VP-->>EN: 下游按节点变量占位符读取
    end
    EN-->>WE: 事件流
    WE-->>CL: SSE text/event-stream（libs/helper.py:424）
```

### 4.4 工作流活动图（并行 / 迭代 / 人工介入）

```mermaid
flowchart TD
    S["开始或触发<br/>trigger_webhook · trigger_schedule · trigger_plugin"] --> Q["问题理解 / 变量整理"]
    Q --> KD{"需要知识?"}
    KD -->|是| KR["knowledge_retrieval<br/>对应 core/rag 的检索管线"]
    KD -->|否| AGN["agent 节点<br/>core/workflow/nodes/agent · agent_v2<br/>策略在 api/core/agent/cot_agent_runner.py"]
    KR --> AGN
    AGN --> PR{"并行分支?"}
    PR -->|是| BR1["LLM 分支"]
    PR -->|是| BR2["工具分支"]
    BR1 --> JT["聚合 / 条件"]
    BR2 --> JT
    PR -->|否| JT
    JT --> IT["迭代与循环节点<br/>Iteration · Loop 容器 handler"]
    JT --> HI["human_input<br/>人工介入后再续跑"]
    JT --> AN["答案 或 代码节点（依赖 sandbox）"]
    IT --> AN
    HI --> AN
    AN --> E["结束 + trace 上报<br/>core/ops/ops_trace_manager.py"]
```

`api/core/workflow/nodes/` 下实测存在的节点族：`agent`、`agent_v2`、`datasource`、`human_input`、`knowledge_index`、`knowledge_retrieval`、`trigger_plugin`、`trigger_schedule`、`trigger_webhook`。注册方式很 Java 味：**`pkgutil.walk_packages` 遍历导入，节点类在装饰器里自注册**（`api/core/workflow/node_factory.py:124-133`），再由 `@lru_cache` 的 `register_nodes()` 汇总成类型映射表（`:266` 附近）。加一个节点 = 加一个文件，不改引擎。

### 4.5 难点与手段

| 难点 | 实际手段（证据） |
|---|---|
| 多租户隔离 | `api/models/account.py` 的 `Tenant` 体系（`:165` 附近可见 `TenantStatus`），业务对象一律挂 `tenant_id` |
| RAG 检索质量 | `core/rag/` 拆成 `extractor → index_processor → splitter → rerank → data_post_processor → datasource/vdb 工厂`，含双索引（parent-child）与 `summary_index` |
| 图执行引擎与业务解耦 | 引擎被抽成独立库 **graphon==0.8.0**（`api/pyproject.toml:49`），dify 侧只做节点实现与事件翻译 |
| 模型 / 工具可插拔 | 全走 `plugin_daemon` 外部进程 + `core/plugin/` HTTP client；出站请求经 `ssrf_proxy` 隔离 |
| 长任务与流式 | Celery `worker` / `worker_beat` 承担异步；SSE 出口 + 中断 API（`completion.py:490` 附近 `ChatStopApi`） |
| 版本升级与配置面 | 47 服务里 34 个 profile 门控；`.env.example` 变量近 300 项 |
| 代码执行的安全 | 独立 `sandbox` 服务；新增 `dify-agent-runtime` 用 **Landlock** 做内核级沙箱（`dify-agent-runtime/README.md:1-12`、`internal/landlock`） |
| 可观测 | `core/ops/ops_trace_manager.py` 统一 trace（Langfuse / Opik 等）+ `extensions/ext_otel.py` OpenTelemetry |

### 4.6 亮点

1. **应用即 DSL**：`api/services/app_dsl_service.py:187 import_app` / `:945 export_dsl`——一个对话应用能被导出成 YAML，进 Git、能 review、能跨环境搬。这是"把 prompt 工程变成工程资产"的落地形态。
2. **节点自注册**：新增能力不碰引擎。
3. **官方把 agent 沙箱下沉到内核层**：`dify-agent`（Pydantic AI）+ `dify-agent-runtime`（Go + Landlock）+ compose 里的 `agent_backend`（`docker-compose.yaml:827`，专用网络 `:1502`）。这条线和你 smolagents 里的执行器抽象是**同一个问题的两种答案**，对照读最值。

### 4.7 边界

不适合：深度定制算法（引擎外置，改执行语义成本高）、轻量私有化（Postgres + Redis + Celery + 多进程是硬依赖）、没有 `sandbox` 服务时用代码节点。

### 4.8 本机实际状态

- `docker/.env` **不存在**，只有 `docker/.env.example`，其中 **`:33 SECRET_KEY=` 是空值**，不填 api 起不来。
- Docker Desktop 装了，但 VM 是否自启必须**当场** `docker info` 查，不能凭记忆断言。
- 所以这份仓库目前的真实用途是**纯源码阅读**。部署前置三项：`cp .env.example .env` + 填 `SECRET_KEY` + 确认镜像源（国内直连 Docker Hub 可能卡，改 `daemon.json` 的 `registry-mirrors` 会影响你以后所有镜像）。**这一步等你点头我才动**（约 3~5 GB 下载、16 个常驻容器、占 80 端口）。

---

## 5 modelcontextprotocol/servers —— 把"工具"从函数升级成协议

### 5.1 定位与解决的问题

MCP 官方**参考实现**仓库（`README.md:3` 明确警告：是教学示例、不是生产方案）。它解决的是集成平台最经典的 **M×N 坍缩**：

```mermaid
flowchart LR
    subgraph BEFORE["没有协议：M 个应用 × N 个工具"]
        A1["App 1"] --> T1["工具 1"]
        A1 --> T2["工具 2"]
        A2["App 2"] --> T1
        A2 --> T2
        A3["App 3"] --> T1
        A3 --> T2
    end
    subgraph AFTER["有 MCP：M + N"]
        B1["App 1"] --> HUB["MCP client<br/>实现一次"]
        B2["App 2"] --> HUB
        B3["App 3"] --> HUB
        HUB --> S1["server 工具 1"]
        HUB --> S2["server 工具 2"]
    end
```

`README.md:12-23` 列了 10 个语言的官方 SDK，**含 Java SDK**——对你主栈最亲近的一条路。

### 5.2 这份代码的真实构成（一个和直觉不符的点）

`src/` 下**只剩 7 个 server**，不是几十个：`everything`、`fetch`、`filesystem`、`git`、`memory`、`sequentialthinking`、`time`。旧的 GitHub / GitLab / Postgres / Slack / Puppeteer 等 **13 个已"毕业"迁到 `servers-archived`**（`README.md:39-53`）。而且 `fetch` / `git` / `time` 已是 **Python** 实现（如 `src/fetch/src/mcp_server_fetch/server.py`），所以这个仓库现在是 TS + Python 混合；`package.json:11-13` 的 workspaces 是 `src/*`。

### 5.3 三个核心原语（用例视角）

```mermaid
flowchart LR
    M["模型 / Agent（brain）"] --> C["MCP Client<br/>宿主，如 Claude Desktop / Qoder"]
    C --> SRV["MCP Server（独立进程）"]
    subgraph PR["server 暴露的三种原语"]
        TO["tools 可执行动作<br/>registerTool"]
        RE["resources 可读数据<br/>registerResource，memory 类 URI"]
        PM["prompts 提示模板<br/>registerPrompt"]
    end
    SRV --- TO
    SRV --- RE
    SRV --- PM
```

| 原语 | 位置 | 长什么样 |
|---|---|---|
| tools | `src/memory/index.ts:780`；`src/filesystem/server.ts:281` 起 14 处；`src/fetch/.../server.py:440` | `server.registerTool("create_entities", { inputSchema: z.object(...) })`；Python 侧是 `@server.tool(name=..., annotations=...)` |
| resources | `src/memory/index.ts:1134`（URI 定义在 `:729`），`:1166` 起支持 `resources/subscribe` 订阅通知 | `memory://knowledge-graph`，mimeType `application/json` |
| prompts | `src/everything/prompts/simple.ts:11` | `server.registerPrompt` |

`src/everything/server/index.ts:180-182` 一次把三类原语全注册了，是最好的"全家福"入门文件。

### 5.4 一次工具调用的序列图

```mermaid
sequenceDiagram
    autonumber
    participant HO as Host（agent 宿主）
    participant CL as MCP Client
    participant SV as MCP Server（独立进程）
    participant TO as 真实副作用（文件 / 网页 / 内存图）
    HO->>CL: 启动子进程（stdio）或连 Streamable HTTP
    CL->>SV: initialize 握手，声明协议版本
    SV-->>CL: capabilities（tools / resources / prompts）
    CL->>SV: tools/list
    SV-->>CL: 名称 + JSON Schema（Zod 生成）+ annotations
    HO->>CL: 模型决定调用某工具
    CL->>SV: tools/call（参数按 schema 校验）
    SV->>TO: 白名单校验后执行
    TO-->>SV: 结果（超长截断或 base64）
    SV-->>CL: content 数组
    CL-->>HO: Observation 回灌给模型
```

传输在 `src/everything/index.ts:22-41` 按 argv 动态 import 三种：`stdio` / `sse` / `streamableHttp`（HTTP 默认端口见 `transports/sse.ts:146`）；其余 TS server 走 stdio（`src/filesystem/index.ts:116-131`）。

### 5.5 难点与安全边界（这一节是精华）

| 难点 | 实际手段（证据） |
|---|---|
| 路径白名单怎么做到不被绕过 | `src/filesystem/index.ts:37-61` 启动时 `realpath` 解析符号链接（防 macOS `/tmp` 逃逸与 symlink 攻击）；`src/filesystem/path-validation.ts:11-105` `isPathWithinAllowedDirectories` 拒绝 null 字节、前缀匹配必须落在分隔符边界（防 `foo` 命中 `foobar`）；写操作用 `O_NOFOLLOW` 拒写被换入的符号链接 |
| roots 动态变更时的竞态 | `src/filesystem/server.ts:226-250` 用 barrier 包装 `registerTool`，白名单刷新期间的调用会等新名单，不会用旧权限执行 |
| SSRF（让服务器替你去访问内网） | `src/fetch/.../server.py:127-136` 判 `ip.is_global`，`:139 _refuse_private_destination` 拦私网 / 回环，**每一跳重定向都重查**（`:340-341`），并强制 robots.txt |
| 客户端怎么知道这个工具危不危险 | 每个工具带 annotations 四元组 `readOnlyHint / destructiveHint / openWorldHint`（`src/memory/index.ts:793-798`、`src/fetch/.../server.py:445-450`），宿主据此决定要不要弹确认 |
| 大输出撑爆上下文 | `fetch` 工具 `max_length` 上限 999999 字符（`server.py:467-470`）；`filesystem` 的 `list_directory` 有 `maxBytes`/`maxFiles` 截断，`read_media_file` 返回 base64（`server.ts:324`） |
| 协议版本迭代 | 同一个 `createServer()` 工厂同时服务 2025-era（`initialize` 握手）与 2026-07-28（`server/discover` 无握手）两代协议 |

### 5.6 亮点

1. **Zod → JSON Schema**：`@modelcontextprotocol/server ^2.3.1` + `zod ^4.2.0`（`src/memory/package.json`），`filesystem/server.ts:44` 用 `z.object(shape).meta({$schema: JSON_SCHEMA_DIALECT})` 强制产出 draft schema——**类型即契约**。
2. **`createServer()` 工厂 + `isEntryPoint` 守卫**：测试能在进程内驱动真实启动路径，而不是 mock。
3. **参考实现的身份**：它不追求功能最多，而是"任何语言的 SDK 都照这个写法对齐"，所以**读码收益高于使用收益**。

### 5.7 同一片天地的三种工具写法（对你最重要的一张表）

| 维度 | `langchain4j @Tool` | smolagents `@tool` / `Tool` | MCP `registerTool` |
|---|---|---|---|
| 形态 | 进程内方法注解 | 进程内函数 / 类 | **独立进程 / 独立服务** |
| 契约来源 | 反射 Java 类型 → JSON Schema | 反射 Python 签名 + docstring | Zod / Pydantic → JSON Schema，协议自描述 |
| 跨语言 | 否（同 JVM） | 否（同进程） | **是**（JSON-RPC） |
| 复用粒度 | 代码复用 | 代码复用 | **协议复用** |
| 权限模型 | 能调这个方法就有权限 | 白名单 + 你自己写的 `guarded()` | allowed directories / roots / annotations / SSRF 代理 |
| 适合 | 企业内部业务动作 | 框架内快速试验 | 想把工具开放给任意宿主或团队 |

### 5.8 本机实际状态

`node_modules` **不存在**（还没 `npm ci`）；本机 node v22.20.0，而 `src/memory/package.json:16` 要求 `"node": ">=24"`。现存 7 个 server **都不需要外部凭据**，外部依赖只是 git / time / fetch 需要 Python + `uvx`。**装不装等你点头**（会占一整棵 `node_modules`）。

---

## 6 你自己写的那部分 —— 从"跑通"到"别人能双击使用"

这部分不是上游代码，但它是这套语料的**交付层**，踩到的坑信息量最大。

### 6.1 `smolagents/my_coding_agent.py`：五只手 + 三圈边界（204 行）

设计原则写在文件头（`:7-11`）：**边界写在代码里，不靠 prompt 求模型自觉**。

```mermaid
flowchart TD
    IN["模型给出 path 或 code 参数"] --> G["guarded() :36-46"]
    G --> C1{"resolve 后仍在 ROOT 内?<br/>ROOT = ai学习，见 :24"}
    C1 -->|否| REJ1["PermissionError 越界"]
    C1 -->|是| C2{"命中 DENY_NAMES? :30<br/>.env .git .venv node_modules __pycache__ .agent-staging"}
    C2 -->|是| REJ2["PermissionError 拒绝凭证或依赖目录"]
    C2 -->|否| C3{"操作类型"}
    C3 -->|读| RD["read_file :49 带行号输出，上限 300 行 / 200 KB"]
    C3 -->|搜| GR["grep_files :92 上限 100 命中，跳过 SKIP_DIRS"]
    C3 -->|写| WF["write_file :128 → 不落原路径<br/>只写 .agent-staging/ 并回 unified diff :140-154"]
    C3 -->|跑| RP["run_python :157"]
    RP --> S1["ast.parse 语法预检 :164-167"]
    S1 --> S2["正则拦 rm / rmtree / remove / unlink / subprocess / socket / urllib / requests :168-170"]
    S2 --> S3["临时目录沙箱 + 清空过的 env，模型拿不到 OPENAI_API_KEY :171-175"]
    S3 --> S4["20 秒超时熔断 + stdout/stderr 截断 :176-182"]
```

三圈闸门的实质：**路径收敛**（`guarded`）、**写操作只暂存**（`.agent-staging/`，要你自己 `cp` 才生效）、**执行环境降级**（空 env + 熔断 + 静态禁词）。

一个必须诚实记录的局限：`run_python` 的禁词是**正则黑名单**，属于"挡住无意"而不是"挡住有心"。真正的安全边界是 smolagents 自己承认的那句话——本地执行器非安全沙箱，不可信代码要换 E2B/Docker（`local_python_executor.py:1692-1693`）。目前这套只在"我自己的目录 + 我自己盯着"的前提下成立。

### 6.2 `smolagents/my_agent.py`：合并成一个 agent，而不是开第二个窗口

`my_agent.py:8` 直接 `from my_coding_agent import ...`，把 5 个自写工具与 2 个业务工具（`MaxDrawdownTool:16`、`AnnualizedVolTool:36`）挂进同一个 `ToolCallingAgent`（`:54-62`），动作空间 8 项（含框架注入的 `final_answer`）。

- **指标口径写在代码里**，不是行业黑话：最大回撤 = 相对历史峰值的最大跌幅，同时回吐发生区间（`:22-33`）；年化波动率 = 日收益率标准差（样本方差，分母 n-1）× √252（`:42-49`）。
- 一个踩过的坑：`my_coding_agent.py` 原本在模块级 `agent = build_agent()`，导致 `import` 就顺手建了第二个 agent 并触发模型初始化；现在建 agent 挪进 `if __name__ == "__main__":`（`:197-202`），**import 无副作用**。
- 成本实测：工具从 2 个变 7 个后，单题累计 input token 从 **2,375 → 19,399**（同口径累计值）。工具变多 ≈ 提示词里的签名变多 ≈ 每步上下文更贵，**这不是免费的功能叠加**。

### 6.3 `smolagents/my_ui.py`：交付外壳里唯一真正的"产品决策"（1,205 行）

#### 6.3.1 三条硬决策（v1.0 立的，v1.1、v1.2 沿用）

```mermaid
flowchart LR
    L["OpsUI(agent).launch()<br/>my_ui.py:1197"] --> D{"share 参数默认值<br/>gradio_ui.py:422 是 True"}
    D -->|"照默认走"| PUB["gradio.live 公网隧道<br/>你的百炼 Key 暴露在公网 URL 上"]
    D -->|"写死 share=False 与 127.0.0.1<br/>my_ui.py:1198-1201"| LOCAL["只有本机能访问"]
    LOCAL --> X["Ctrl-C 后端口释放但进程挂在非守护线程<br/>→ 显式 os._exit(0)，my_ui.py:1205"]
```

验证口径两条，缺一不可：日志里**没有** `gradio.live`；`lsof -nP -iTCP:7860 -sTCP:LISTEN` 只出现 `127.0.0.1`。

第三条是**结构性的**：不改上游一行源码。所有界面增强都写在 `OpsUI(GradioUI)` 子类里，`_stream_response` 自己维护那份内部列表、每次 `yield list(msgs)` 交副本给 gradio（`my_ui.py:923`；v1.1/v1.2 是 `list(msgs) + [stats]` 在 `:310`，v1.3 把统计并进了步骤卡，见 6.3.5）。收益是上游升级时冲突面只有这一个文件；代价是 gradio 那套折叠语义你得自己摸清（见 6.3.2 的坑、6.3.4 里 v1.2 换壳踩的那几脚，以及 6.3.5 里 D4 那条 `ValidationError`）。

#### 6.3.2 v1.1 加的两层：成本上墙 + 真刹车

**成本卡。** 每步之后追加一条 `gr.ChatMessage`，数字写在 **`metadata.title`** 上：

```
📊 第 3/8 步 · 本题累计 in 12,345 / out 678 token · 本步 4.2s        （· 本步报错）
```

**v1.3 起这条独立卡不再单发**：一个 step 只出一张卡，上面那串数字并进了步骤卡的标题（`_step_card`，`:672-727`；标题拼装 `:705-710`，末行 `:721-724`），三档口径一字未改。下面这张表和"为什么写在 title 里"那条实测结论仍然照旧成立。

这不是审美选择，是被实测逼的：gradio 会把带 `metadata.title` 的消息折成组，**收起状态时正文根本不在 DOM 里**。第一版把数字写正文，界面上一个字都看不见。点开是三行明细，三个口径**写死不混**：

| 口径 | 取法 | 为什么单独一档 |
|---|---|---|
| 本步 | `cur[-1]` 的 `timing.duration` / `token_usage` | `Timing.duration` 可能是 `None`，必须 `or 0.0` |
| 本题累计 | 最后一个 `TaskStep` 之后的所有 `ActionStep` 求和 | `GradioUI` 默认 `reset_agent_memory=False`（`gradio_ui.py:310`），记忆跨题累积 |
| 进程累计 | `agent.monitor.get_total_token_counts()` | 与日志 `[Step N]` 逐位相符，用来证明前两个不是我自己算着玩的 |

顺带一个容易误判的点：卡里的"第 N 步"是**本题内**（`agents.py:543` 每次 `_run_stream` 置 1），控制台 `[Step N]` 是**进程内**（`monitoring.py:108` 的 `len(self.step_durations)`）。从第二题起这两个数**必然不同**，不是 bug。

**刹车。** 停止按钮本来就在（gradio 6.30 的 `stop_btn` 默认 `True`），缺的是"点了真停"。下图是 v1.1 立的链路——`_stream_response` 那层 `finally` 在 v1.2 换壳时**一字未改**搬了过来，但触发它的人变了（v1.2 的按钮是自建的，见 6.3.4）；v1.3 又搬了一次：**agent 挪进 worker 线程**，于是"关内层生成器"这一步只能跟着挪进那条线程的 `finally`（`:800-808`），`_stream_response` 的 `finally` 只剩三个动作——置放弃标记、`interrupt()`、结算待批（`:928-937`）：

```mermaid
sequenceDiagram
    participant U as 你
    participant G as gradio 自建 Blocks
    participant O as OpsUI._stream_response<br/>my_ui.py:810-937
    participant W as _worker 线程<br/>my_ui.py:785-808
    participant A as MultiStepAgent._run_stream<br/>agents.py:540-611
    U->>G: 点「■ 停止」
    G->>O: 关掉这层生成器（finally 在 :928）
    O->>A: agent.interrupt() → interrupt_switch=True（agents.py:754）
    O->>W: _abandoned.set()（:935）→ 那个 for 循环下一轮 break
    O->>W: 生成器被弃 → 它的 finally 在起它的线程里 inner.close()（:805）
    W->>A: 内层被关；agents.py:599-602 的 finally 里还有一次 yield → RuntimeError
    A-->>W: 该 RuntimeError 由 W 自己吃掉（:806-807），否则 stderr 每次 Stop 喷一条 GeneratorExit
    Note over A: 正在执行的那一步继续跑完，不受 stop 控制
    A->>A: 下一个 while 顶部检查 interrupt_switch → raise AgentError（:545-547）
    A-->>U: 不再进第 N+1 步；日志 [Step …] 行数停止增长
```

语义一句话：**stop 是在步边界停，不打断正在执行的那一步**。实测那条 `time.sleep(30)` 最终是被 `run_python` 自己的 20 秒沙箱超时掐掉的（日志 `Observations: 超时 20 秒，已杀掉`），不是被 stop 掐的。要瞬间掐断得动执行器，不在这条工单里。

停止之后服务照常用：`interrupt_switch` 由下一次 `run()` 在 `agents.py:470` 重置回 `False`，**不需要重启**。实测停完再问一题，1.22 秒出 `Final answer: 2`。

#### 6.3.3 D1：一行 `mkdir` 放错位置，整条执行工具就挂

`run_python` 拿 `ai学习/.agent-staging` 当 `tempfile.TemporaryDirectory(dir=…)` 的父目录（`my_coding_agent.py:174`），目录不存在就是裸 `FileNotFoundError`。原来那句 `STAGING.mkdir()` 写在 `if __name__ == "__main__"` 分支里，而 UI 的真实链路是 `my_ui.py:15 → my_agent.py:8 → from my_coding_agent import …`（v1.2 前那条 import 在 `my_ui.py:10`，更早 `:4`）——**import 不执行 `__main__`**。目录当时存在，只是因为历史上直接跑过一次 `my_coding_agent.py`，属于**靠巧合活着**。

v1.1 把它提到模块级（`my_coding_agent.py:26-28`），并成对复现验证：把目录挪开后，旧代码 `import 后目录存在: False` + `FileNotFoundError`，新代码 `True` + `run_python: 'exit=0\n42\n'`。

#### 6.3.4 v1.2 换壳：`ChatInterface` 换成自建 `Blocks`，多出一层 SQLite 显示库

v1.2 把界面从"框架给的默认形态"改成"侧栏 + 状态条 + 深色"。**agent 侧一行未动**，全部改动落在 `my_ui.py`（76 → 462 行）。链路现在是两条正交的：提问链路走 `_respond`，回看链路走 `History`，两者只在"消息列表"这一个数据结构上相遇。

```mermaid
flowchart TD
    B["MultimodalTextbox<br/>submit_btn=True · stop_btn=False"] -->|"box.submit"| R["_respond(message, sid)<br/>my_ui.py:1004-1066"]
    R --> U["_user_message<br/>:988 自建用户气泡"]
    R --> S["_stream_response<br/>:810 v1.1 的刹车语义原样保留<br/>v1.3 起它只是取队列的壳"]
    S --> W["threading.Thread → _worker :785<br/>agent.run(stream=True)"]
    W --> AG["MultiStepAgent._run_stream<br/>agents.py:540-611"]
    W --> GT["工具实例上的审批门<br/>_gated_call :571（见 6.3.5）"]
    S --> ST["_stats :730 一份数字"]
    ST --> C1["_step_card :672 一步一张卡<br/>卡末行就是原来的统计卡"]
    ST --> C2["_status_html :761 顶部胶囊<br/>有待批时多一颗「待批」"]
    R -->|"每 yield 一次 · 7 元组"| OUT["chatbot / status / radio / box / sid / allow / deny"]
    R -->|"finally"| H["History.save 整条覆盖写<br/>:451，DELETE 在 :463"]
    H --> DB[(".agent-history.sqlite3<br/>sessions + messages")]
    L["demo.load :1192"] --> DB2["History.choices / load"] --> OUT
    SB["■ 停止 :1155"] -->|"interrupt + 结算待批"| AG
```

四个非显然的实现点，每一个都是实测撞出来的：

1. **为什么不能继续用 `gr.ChatInterface`**：它的 `_setup_events()` 在 `__init__` 里就跑完了（`chat_interface.py:265`），构造完之后**没有口子**往消息流旁边插侧栏、也没有口子把状态条提到输入框上方。所以 `create_app()`（`my_ui.py:1135-1193`）整体覆盖成 `gr.Blocks`，只继承 `GradioUI` 以复用它的 `agent` 装配与 `_stream_response` 上游实现。
2. **用户气泡没人拼了**：`GradioUI._stream_response` 交出来的一直只有 assistant 那一串，以前是 `ChatInterface` 替你补上用户那句；换成自建 Blocks 后屏幕第一行会凭空消失、库里也没有。**必须自己拼**（`_user_message()`，`:988-1002`），而且只拼显示、不重跑 `_process_message`——那句会把上传文件真复制一份。
3. **gradio 自带的 stop 键在 Blocks 下是死的**：`MultimodalTextbox(stop_btn=True)` 那个按钮的取消链路只有 `ChatInterface` 会接（`chat_interface.py:371-372` 把按钮摘下来自己管）。实测在 `步数 7/8` 点它，照样跑到 `9/8` 才完。所以 `stop_btn=False`，刹车改由 `:1155` 的自建「■ 停止」→ `_stop()`（`:1076-1096`）→ `agent.interrupt()`，与 6.3.2 那条 `finally` 是**同一个开关的两个触发源**（v1.3 起这个触发源还要多结算一次待批，见 6.3.5）。
4. **刷新页面不重跑 `create_app`**：Radio 的 `choices` 还停在建应用那一刻的空表，实测重载后侧栏是空的——这恰好是 V3 要消灭的那个缺陷。解法是挂 `demo.load`（`:1192`，回调 `:1118-1132`）把库里的会话重新推一遍，并自动展开最新一条。v1.4 起这条回调**同时把 `sid` 指到那条会话**，见 6.3.6。

`History`（`:382-497`）管**三张表**：`sessions(id, title, created_at, updated_at)` 与 `messages(id, session_id, ord, role, content, meta, …)` 是显示层，v1.5 追加的 `memory(session_id PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE, payload, updated_at)` 是模型层（见 6.3.7）。外键都带 `ON DELETE CASCADE`，`memory` 的 DDL 是 **additive** 的——老库直接被新代码多建一张表，v1.4 的代码反过来读新库也不碰它。五个约定值得记住：

| 约定 | 位置 | 为什么 |
|---|---|---|
| `DB_PATH` 用 `Path(__file__).resolve()` 而不是 cwd | `:30` | 启动器 `cd smolagents` 与否都落在同一个文件，避免"换个起法历史就看不见了" |
| `save()` 是**整条覆盖写**（先删后插全量） | `:451-472`，`DELETE` 在 `:463` | 半截停止的那次也落库；重复保存不会产生双份消息。所以调用方必须喂**完整列表**——v1.4 的 D5 修的就是这个前提（见 6.3.6）|
| 标题取首条 user 消息前 **28** 字，且只在仍是「新会话」时写；`updated_at` 每次存都刷 | `:458-459` 取值，`:469-472` 那条 `CASE WHEN title = '新会话'` | 侧栏一行放得下；重存不会把标题改掉；v1.4 修掉「有了标题就再也不刷新时间」的 D6 |
| `choices()` 按 `updated_at DESC` 取，上限 **50** 条 | `:434-439` | 不搜索、不分组、不分页——这是 v1.2 的已知边界 |
| `save_memory()` 是 `INSERT OR REPLACE`，**一条会话一行**（主键就是 `session_id`），返回存了多少字符 | DDL `:410`，方法 `:474-482`，读回 `:484-487` | 和 `save()` 同样是覆盖式，所以调用方给的必须是**整份** steps；返回字符数是为了把"记忆有多大"直接写进日志和断言 |

`meta` 列存的是 `gr.ChatMessage.metadata` 的 JSON（`role`/`content` 各自一列，`:455-460` 先用 `dataclasses.asdict` 把 dataclass 拍平成字典再拆），`load()` 拿它重建 `gr.ChatMessage`（`:448`），所以折叠卡、报错条这类带 `metadata.title` 的消息能原样贴回来。**但库里那两串字不等于模型记得的东西**——`messages` 是"屏幕上说过什么"，`memory` 才是"模型下一轮读到什么"，两份各自覆盖、各自落库（v1.4 之前只有前者，这就是当时"重启后模型答不记得"的根因，v1.5 补的是后者，见 6.3.7）。`reset_agent_memory` 仍为 `False`（见 6.3.2），所以同一会话内模型那一边的 steps 一直往上长。

深色壳（`DARK_CSS`，`:217-336`）分两类活：一类是 `:root` 变量同名覆盖（`--body-background-fill` 等，gradio 6.30 自己吐在根上的那批），另一类是**定点压制 gradio 硬编成白色的六个位置**——块标题 `rgb(255,255,255)`、secondary 按钮 `rgb(228,228,231)`、气泡底 `rgb(250,250,250)`、`layout="panel"` 下的 `.message-row`（user `rgb(255,247,237)` / bot `rgb(250,250,250)`）、折叠卡 `.thought-group`、页脚。前四个都是从浏览器 `getComputedStyle()` 里读出来的实测值，不是猜的。另外 `layout` 必须给 `"panel"`：默认 `"bubble"` 会把消息列按内容收缩，实测折叠卡只有 **353px**（容器 950px），这就是第一版截图里右边空一大片的原因。v1.3 在这段 CSS 里追加了审批相关的规则（`:269-279`：待批胶囊的描边、`#approve-btn` / `#deny-btn` 的配色），没有另起一个 CSS 块。


#### 6.3.5 v1.3：审批门套在工具实例上，agent 挪进另一条线程

V4（步骤卡片化）+ P0-2（工具执行前审批）同批。`my_ui.py` **462 → 850 行**（对 `.rollback/v1.2` 的 `diff`：+432 / −44），`my_coding_agent.py` **一字未动**（`cmp` 与 `.rollback/v1.2`、`.rollback/v1.3` 两份存档都一致）。功能面也没变：仍是 7 项工具、`max_steps=8`、`qwen-plus`、单会话 `7860`。

**门套在哪：`BaseTool.__call__` 的最后一行。** `tools.py:231-249` 的 `__call__` 收尾是 `return self.forward(*args, **kwargs)`，而 Python 查属性时**实例字典优先于类上的 `staticmethod`**——所以在实例上盖一个 `forward` 属性就能拦住执行，`__call__` 前面的入参校验和后面的 `output_type` 包装全都不受影响。套法见 `_install_gate`（`:546-569`）：`copy.copy(base)` 换一个新实例再盖（`:560`、`:567-569`），**不去改 `my_coding_agent.py` 里那批模块级 `@tool` 对象**。三处不显然的细节：

- `gated.__signature__ = inspect.signature(original)`（`:566`）。不保签名的话，`*a, **kw` 会把参数吞成一个元组，审批卡就写不出「要往哪写、写什么」。有了它，`bind_partial(*args, **kwargs).arguments`（`:574`）能把参数还原成字典——**展示用的和执行用的是同一份**，不是我先格式化再另算一遍。
- 幂等标记 `_opsui_gated`（`:558`、`:568`）。多个 `OpsUI` 实例（离线测试里反复建）不能把门套成两层：两层就是问两遍，点一次「允许」只解开外面那层，里面那条线程永远挂在 `wait()` 上。
- `_pending` 和 `_gate_lock` 挂在**类**上（`:511-512`），不是实例上。因为门守的是**进程里那一个 agent** 的工具，第一个实例装好门之后别人不再重装；队列若放实例上，就会出现「A 装的门把单子递给 A，屏上看单的是 B」——按钮永远不亮。

**只拦会动东西的两只手。** `GATED_TOOLS = ("write_file", "run_python")`（`:34`）；`read_file` / `list_dir` / `grep_files` 不弹审批，否则一次检索三连问要点三遍，比不加还慢。`final_answer` 也不拦——它是交卷不是副作用。

**为什么非得换线程。** 审批是**阻塞**的，而 gradio 是**同步往前推**那条流式生成器的：工具卡在 `forward` 里等点按钮 → 生成器 yield 不出审批卡 → 界面上根本没有「允许」可点 → 死锁。所以 v1.3 把 `agent.run(stream=True)` 挪进 `_worker` 线程（`:785-808`），事件塞 `queue.Queue`；`_stream_response`（`:810-937`）变成一条**只取队列**的壳，用 `q.get(timeout=0.25)`（`:841`）驱动。关键一点：**空转的那 0.25 秒也要走一遍渲染判定**（`:898-920`），否则待批卡要等下一个 agent 事件才画得出来——而下一个事件永远不来，因为 agent 正卡在这道闸上。

```mermaid
flowchart TD
    T["提问 box.submit"] --> RS["_respond :1004<br/>7 元组输出"]
    RS --> SR["_stream_response :810<br/>UI 线程 · q.get 0.25s"]
    SR -->|"起线程"| WK["_worker :785<br/>agent.run stream=True"]
    WK --> LOOP["MultiStepAgent 主循环<br/>agents.py:540-611"]
    LOOP -->|"模型要调 write_file 或 run_python"| CALL["BaseTool.__call__<br/>tools.py:231-249"]
    CALL -->|"self.forward 已被实例属性盖住"| GATE["_gated_call :571<br/>Approval 入类级 _pending :511"]
    GATE --> WAIT["ap.wait 600s :374<br/>只阻塞 worker 这一条线程"]
    SR -->|"每轮扫 _pending_snapshot"| CARD["_approval_card :621<br/>🟡 待批 · 参数原样贴出"]
    CARD --> BTN{"你点哪个"}
    BTN -->|"✔ 允许 :1189"| OK["_decide allowed :604<br/>decision + Event.set"]
    BTN -->|"✖ 拒绝 :1190"| NO["_decide denied"]
    BTN -->|"■ 停止 :1186"| STOP["_stop :1076 → _settle_all cancelled :616"]
    OK -->|"闸放行"| EXEC["original 真执行<br/>沙箱与三圈闸门照旧"]
    NO --> OBS["观察值 DENIED_OBSERVATION :50<br/>写明未产生任何副作用"]
    STOP --> OBS
    WAIT --> OBS
    EXEC --> STEP["_step_card :672<br/>🟢 成功 · 秒 · token"]
    OBS --> STEP
```

**一条流上现在有三种卡，身份存对象不存下标。** 流式思考气泡（`:846-857`）、审批卡（`:898-920`）、步骤卡（`:858-884`）都往同一个 `msgs` 列表里写。审批卡按 `ap.id` 存**卡片对象**（`:833`、`:905-906`），更新时**原地改** `content` / `metadata`（`:913-914`）——因为步骤事件到达时会 `pop` 掉那条流式气泡（`:860`），任何存过的下标从那一刻起都不作数（踩过：按下标写回，把刚生成的步骤卡盖成了审批卡）。摘单也挪到"画上收尾状态之后"（`:917-920`）：先前有一版只在更新分支里摘，结果**点得快**的那张卡第一次落笔时 `decision` 已经是 `allowed`，单子就永远留在队列里越积越多（也踩过）。

**V4：一个 step 一张卡。** `_step_card`（`:672-727`）把上游那 5~6 条无差别折叠卡并成一条，标题带工具名、结果色点、秒数和 token（`:705-710`），正文依次是模型思考、调用参数、结果、报错，末行是本题累计（`:721-724`）。数字仍然必须写进 `metadata.title`——带 `title` 的消息 gradio 会折起来，收起时正文根本不在 DOM 里（6.3.2 那条实测照旧成立）。

**三种"没执行"分开标，三处措辞要对得上。** 拒绝 / 停止取消 / 超时无人批，在审批卡上是 `DECISION_LABEL`（`:41-47`）的「已拒绝 / 随停止取消 / 超时未批」，在步骤卡上是 `DENIED_VERDICT`（`:55`）的「已拒绝 / 已取消 / 超时未批」，交回模型的是 `DENIED_OBSERVATION`（`:50-54`）三条写明"未产生任何副作用"的话。步骤卡靠正文反查命中哪一条来上色（`:691`），所以**这三个字典必须同步改**，改一个不改另两个就会出现"审批卡说取消、步骤卡说拒绝"。

**停止要多结算一处。** `_stream_response` 的 `finally`（`:928-937`）现在是三件事：`_abandoned.set()`（让 worker 的 `for` 下一轮 break）、`agent.interrupt()`、`_settle_all("cancelled")`。第三件是 v1.3 新加的——不然「停止」只把界面停住，worker 线程还挂在 `wait()` 上，`agent` 也就永远占着。换题开局同样先结算再摘除（`:813-815`）。

**D4：`metadata.status` 只有两个字面值。** gradio 6.30 的 `chatbot.py:55` 把它定成 `Literal["pending","done"]`。v1.1 起那条停止气泡一直写的是 `"complete"`，没人发现——因为**没人真在停止后去数气泡**；本轮实测一停，gradio 在 postprocess 抛 `ValidationError`，被包成 `ComponentProcessingError`，**整条 chatbot 输出直接丢掉**。已改成 `"done"`（`:1053`）。这条坑的通用形态是：折叠卡里任何字段不合 schema，掉的是整个输出而不是那一条。

**边界，四条都得记着**：命令行 `python my_coding_agent.py` 直调工具**完全不过闸**（门是 UI 装的，设计如此）；一步里多个工具调用会走 `ThreadPoolExecutor`（`agents.py:1361-1437`），队列里能同时躺多条待批，而按钮只结算**最早**那条（`:584`）；`APPROVAL_TIMEOUT = 600.0`（`:36`）的超时分支只在离线测过，**线上 600 秒没等过**【未验证】；`PlanningStep` 那张 🧭 卡（`:648-653`）本轮三次在线跑**都没触发**【未验证】。

#### 6.3.6 v1.4：屏上的消息列表和 `agent.memory` 都按会话走

D5（连问吞前一题）+ V5（点旧会话接着聊）同批，顺带修掉 D6（侧栏 `updated_at` 不刷新）。`my_ui.py` **850 → 893 行**（对 `.rollback/v1.3` 的 `diff`：`+70 / −27`），审批闸、步骤卡、状态条档位**一字未动**。

**D5 是三处叠在一起才成立的**，单独看任何一处都像"没毛病"：① `_respond` 每一轮从 `last = [user_msg] + msgs` 起，而 chatbot 的输出是**整体替换**；② `History.save()` 是 `DELETE FROM messages WHERE session_id=?` 的**整条覆盖**（`:451-472`，`DELETE` 在 `:463`）——它只有在调用方喂进**完整列表**时才等价于追加；③ `sid` 同时挂在 `box.submit` 的 inputs 和 outputs 上（`:1178-1182`），所以第二轮**沿用同一条会话**。三条凑齐 = 新的一题把旧的一题从屏上和库里**一起**抹掉。修法因此也只能是一条：起点从库里那一串起（`base = self.hist.load(sid)`，`:1013`；每一帧 `last = base + [user_msg] + list(msgs)`，`:1028`）。**覆盖语义一个字都没改**，改的是喂给它的那串。

**V5 的核心动作只有"换引用"这一件事。** `_bind_memory(sid)`（`:940-965`）把 `agent.memory` 指向 `_mem[sid]`（`:541-542` 那两个字段），依据是框架的两行事实：`GradioUI` 默认 `reset_agent_memory=False`（`gradio_ui.py:310`，实际传参在 `:389`），而 `agents.py:477` 每次 `run()` 都会把 `system_prompt` 同步进"当前那份 memory"——所以**新任务追加到谁身上，取决于起 worker 那一刻 `self.memory` 指向谁**。三个不显然的取舍：

- **不传 `reset=True`**：`agents.py:478-480` 里 `memory.reset()` 和 `monitor.reset()` 是绑在一起的，一 reset 就把"进程累计"这档口径清零，状态条上那颗数就废了。
- **不在跑到一半换**：worker 线程正在读 `self.memory.steps`，中途换引用等于把一条会话的历史灌进另一条的当前步，`_stats()`（`:730`）那条"最后一个 `TaskStep` 之后"的本题边界也会跟着错位。所以只在 `_respond` 开头调（`:1009`）。
- **`AgentMemory` 当时不落库**：`memory.py:214-232` 没有任何 (de)serializer，框架也没给序列化口子。于是记忆的生命周期＝进程的生命周期，这条是 V5 剩下的那一半，v1.4 写进了遗留清单——**v1.5 由 V6 补上**（自己写编解码、加一张 `memory` 表，见 6.3.7）。

```mermaid
flowchart TD
    Q["提问 message + sid"] --> EN["hist.ensure(sid) :489"]
    EN --> BM["_bind_memory(sid) :940"]
    BM --> J{"_mem_sid == sid ?"}
    J -->|"同一条会话"| KEEP["agent.memory 不动<br/>框架往上追加 TaskStep"]
    J -->|"换了一条"| NEW{"_mem 里有吗"}
    NEW -->|"没有"| MK["新建 AgentMemory<br/>memory.py:214-232 无序列化口子"]
    NEW -->|"有"| GOT["取回那份旧的引用"]
    MK --> SWAP["self.agent.memory = 它<br/>只换引用，从不 reset()"]
    GOT --> SWAP
    SWAP --> BASE["base = hist.load(sid) :441"]
    KEEP --> BASE
    BASE --> RUN["worker：agent.run stream=True<br/>reset=False 是 gradio_ui.py:310 的默认"]
    RUN --> FR["每一帧 last = base + 本题 + 本轮流<br/>:1015 与 :1028"]
    FR --> SV["finally：hist.save(sid, last) :1058<br/>整条覆盖，所以喂进去的必须是完整列表"]
    SEL["侧栏 radio.change :1185"] -->|"交出第三个值 int(sid) :1116"| BM
    LD["demo.load :1192"] -->|"最近一条的消息 + 它的 sid :1132"| BM
```

**`sid` 必须是一条**能同时喂给 chatbot 和 State 的输出，这是 V5 接线的地方。** 三处一起改：`radio.change` 的 `outputs` 多带 `sid`（`:1185`）、`_select_session` 交出 `int(sid)`（`:1098-1116`）、`demo.load` 的回调把 `_on_load` 从闭包提成方法（`:1118-1132`）并同样交出 `sid`。为什么刷新那条也要给 `sid`：屏上显示的就是最近一条会话，`sid` 空着的话下一条提问会另开一条，而屏幕是**整体替换**——刚看到的那串字当场找不回来，那就是 D5 的第二条路径。提成方法还有个附带收益：它能被离线用例直接调（53 条断言里的 7a/7b/7c 就是这么打的）。

**D6 是修 V5 时顺带撞出来的。** `History.save()` 那条 UPDATE 从 v1.2 起挂着 `WHERE id = ? AND title = '新会话'`，于是会话**一旦有了标题就再也不刷 `updated_at`**，而侧栏排序用的正是 `ORDER BY updated_at DESC`。以前这只影响"刷新页面看到哪一条"，现在决定"下一条提问落进哪一条会话"——顺序错了等于问错地方，所以改成无条件刷时间、标题用 `CASE WHEN title = '新会话' THEN ? ELSE title END` 保住（`:469-472`）。离线 8c 就是这条的正向断言：老会话一有动作就回到第一。

**口径变了多少，实测说清。** token 三档（本步 / 本题累计 / 进程累计）一个没动，但**同一会话内每题的 input 会往上爬**：模型每次收到整段会话历史。实测 `2,362 → 2,464 → 2,564`（每题 **约 +100**，正好等于上一题的一问一答），点「＋ 新会话」回到 **2,363**；`monitor` 不被 reset，所以进程累计仍是各问之和（s5 收尾 `in 15,176` = 五问相加）。另外 `save()` 是覆盖式重插，`messages.rowid` 每轮跳号（实测 `1,2,3 → 4..9`，再往后 `20..33`），**顺序与去重一律看 `ord`，别看 `rowid`**。

**三条边界要记着**：① ~~记忆只在进程里~~——这是 v1.4 的状态（重启后旧会话的字还在屏上，模型却答「不记得」，实测那题 `in 3,384` 没带上会话历史），**v1.5 的 V6 把这一半补上了**，见 6.3.7；② **`_mem_sid` 是单值**，两个标签页同时问会互相抢"当前绑到哪条会话"（`monitor` 同样共享），设计前提仍是**一次只问一题**；③ ~~**点侧栏之后高亮不跟**~~——`_select_session` 交出了 `sid`，但 `#sessions input` 的 `checked` 实测仍是 `0`，屏和内容接上了、视觉没接上（纯界面层）。③ 在 v1.5 造成了真后果、立单 V7，**v1.6 已把整条"高亮 ≠ 绑定"修掉（不止点侧栏这一路，还有「＋ 新会话」和刷新页面两条），见 6.3.8**。【订正一条测法：那句 `checked` 仍为 `0` 是用合成点击（`label.click()` / `dispatchEvent`）测的，v1.6 实测**合成点击在 gradio radio 上本就不可靠**，必须用 CDP 真鼠标 `mousePressed`/`mouseReleased`；v1.6 那张 before/after 表里"点从没亮过的另一条"在两个版本下都正常切换，真 bug 只在**值没变的那一次**。】

#### 6.3.7 v1.5：`agent.memory` 落库（重启后模型那一边接着记得）+ 停止落在待批之前不再死停（V6 + D7）

范围按工单号锁 **V6 + D7**。`my_ui.py` **893 → 1,108 行**（44,838 → **55,774 B**，对 `.rollback/v1.4` 的 `diff` 净 **`+217 / −2`**）。`my_coding_agent.py` **204 行未动**，上游源码零改动（`git diff --name-only` 为空；`git status --porcelain` 里除了三个 `my_*.py` 只多一个应用自己建的 `.agent-history.sqlite3`，它没有被 `.gitignore` 收掉）；审批闸、步骤卡、状态条三档口径**一行没碰**。

**V6 的判据只有一句话：模型读的是 `memory.steps`，不是屏上那串卡片。** `agents.py:767-769` 的 `write_memory_to_messages()` ＝ `memory.system_prompt.to_messages()` ＋ 逐条 `step.to_messages()`。所以"重启后还记得"的正解不是把屏幕文字重放一遍——重放要重新定义「本题累计」的边界，而且 `in` 会随历史**线性涨**；存**字段本身**才既保住边界又不多带一个字。存哪些字段也有根据：`memory.steps` 里只会出现 `TaskStep` / `ActionStep` / `PlanningStep` 三种（`FinalAnswerStep` 只 yield 不 append，`agents.py:609-611`；步数用满时 `:636` append 的是**带 `AgentMaxStepsError` 的 ActionStep**），白名单 `MEM_FIELDS`（`my_ui.py:64-79`）就是按 `to_messages()` 实际读到的字段列出来的。

**难度全在编解码上，五个坑每一个都是踩出来的：**

- **不存的三样**：`model_input_messages`（整段提示词，存一份等于 O(n²)）＋图片三兄弟 `images` / `image_outputs` / `model_output_images`。后果写死在边界里——**带图的观察值重启后进不了模型上下文**【本轮题面全是纯文本，多图会话【未验证】】。
- **文本必须原样存**：只有 `action_output` 过 `make_json_serializable`。因为 `utils.py:146-153` 会把**长得像 JSON 的字符串解析成 dict**，一路 `json.dumps` 再回灌，观察值 `{"ok": true, "n": 73}` 就变字了（离线断言 1c 逐字钉这条）。
- **错误对象是"造"出来的，不是"构造"的**：`AgentError.__init__(message, logger)` 里 logger 必需、而且会**当场** `log_error`。所以 `cls.__new__(cls)` + `Exception.__init__(err, message)` 再手设 `.message`（`:92-107`）。能落库的只有**类名**，所以 `_error_types()` 沿 `AgentError.__subclasses__()` 递归建类名索引（`:82-89`）——恢复出来 `type(step.error).__name__ == "AgentParsingError"`，步骤卡的「🔴 报错」判定才不塌。
- **两个 dataclass 是派生字段**：`Timing.duration` 是 property、`TokenUsage.total_tokens` 是 `init=False`，`dict()` 出来的键比构造参数多，只能挑着交（`:110-120`）。
- **`ToolCall` 用 `tc.dict()`**（OpenAI function 形状），不是 `dataclasses.asdict`。

坏数据的降级路径是**分层的**（`decode_memory`，`:157-213`）：整块坏 JSON / `fmt` 不符 / 顶层不是 dict → 返回 `[]`，当作这条会话没记忆，正常开新会话；单条坏 → `except (TypeError, ValueError, AttributeError): continue`，跳过那一条、其余照灌。**不会因为一次异常把整条会话废掉。**

```mermaid
flowchart LR
    subgraph P1["进程 1：跑完就关了"]
        A1["agent.run 往 memory.steps 上追加<br/>agents.py:477"] --> A2["encode_memory(mem.steps)<br/>my_ui.py:123-154"]
        A2 --> A3["_respond 的 finally：两个条件<br/>mem is not None 且 _mem_sid == sid<br/>my_ui.py:1064-1065"]
    end
    A3 --> T[("memory 表：一行一个 session_id<br/>INSERT OR REPLACE · my_ui.py:410 与 :474-482")]
    T --> B1["重启后 _bind_memory 未命中<br/>decode_memory(load_memory(sid))<br/>my_ui.py:960-962"]
    B1 --> B2["mem.steps.extend(steps)<br/>system_prompt 与 monitor 一律不动"]
    B2 --> C1["write_memory_to_messages()<br/>agents.py:767-769<br/>＝模型这一轮读到的那一串"]
```

**接进去只有三处，两处刻意保持小。** `History` 加一张 additive 的表（DDL `:410`，方法 `save_memory` `:474-482` / `load_memory` `:484-487`）；`_bind_memory`（`:940-965`）在进程内 `_mem` 未命中时回灌 steps——**只灌 steps**，`system_prompt` 由框架自己在 `run()` 开头同步，`monitor` 更不能动（否则「进程累计」作废，见 6.3.6）；`_respond` 的 `finally`（`:1056-1066`）在 `hist.save(sid, last)` 之后紧接着存记忆。**那两个条件不能省**：`mem is not None` 让没绑定记忆的一题不去建行，`self._mem_sid == sid` 是**会话归属**判据——中途有人换了会话，就不能把别人的记忆盖到这条上。worker 线程可能还在跑（页面被刷新的那一路），所以这一步**可能存下半截**，下一题结束时再存就整了：半截可接受、存错会话不行。

**实测走的是交付形态 7860、真 qwen-plus、两次真重启**（`关闭Agent.command`，pid `45372 → 46527 → 49146`）：

| 路 | 结果 |
|---|---|
| 记住 73 → 同会话追问 | `in 2,362` → `2,465`，进程累计 `4,827/34` |
| **重启**后点旧会话再问 | `Final answer: 73`，**`in 2,574`**（裸起步 `2,363`，说明历史真带上了）；进程档归零重算 `4,937/34` |
| 同一条继续聊 | `Final answer: 73`，`in 2,675`，进程 `7,612/51` |
| **工具观察值**也带着（审批跑 `print(3*7)` → **第二次重启**再问） | `Final answer: 21`，`in 3,091`、进程 `3,091/17`；库里那条 ActionStep 的 `observations` 是逐字的 `exit=0`⏎`21` |
| 点「＋ 新会话」问同一题 | `Final answer: 不记得`，`in 2,363` —— 持久化只针对聊过的那条，**隔离没漏** |
| 库里形状 | 首轮 2 问之后 session 1 的 payload **1,029 字符 / 4 步**，全部跑完 **4,042 字符 / 15 步**；表 4 张（`sessions` / `messages` / `memory` / `sqlite_sequence`） |

**D7 的根因是框架清了开关，不是按钮没生效。** `agents.py:470` 在每次 `run()` 开头把 `interrupt_switch` 清回 `False`，所以 `■ 停止` 落在待批卡**出现之前**（v1.4 实测 0.2s 那一下）中断的是一条**空闲的** agent——等于空放；随后到达的那条待批没人结算，界面死停「等待审批」**142.4s**（`APPROVAL_TIMEOUT` 是 600s，不会自己解），要手动补 ✖ 才解开。修法是四处，缺一条窗口就还开着：

1. **类级**计数器 `_run_seq` / `_cancelled_before`（`:516-517`）。闸装在**进程唯一**的那个 agent 上，所以计数器必须和 `_pending`、`_gate_lock` 同侧（也是类级，`:511-512`）；放实例上就出现"A 领的号管不住 A 装的那道门"。
2. **开跑先领号**：`_stream_response` 在计数器归零之后、**起 worker 线程之前**`OpsUI._run_seq += 1`（`:824-825`）。号没领上就开工，闸读到的还是上一轮的号。
3. **入队与判停在同一个临界区**（`_gated_call`，`:583-586`）：`with self._gate_lock: self._pending.append(ap); if OpsUI._run_seq <= OpsUI._cancelled_before: ap.decide("cancelled")`。两种到达顺序都被覆盖——闸先拿到锁，单子已在队里，随后 `_stop` 的 `_settle_all` 必定看得见；`_stop` 先拿到锁，这里入队时立刻自判 `cancelled`，压根不等人点。**"先查后入队"那个缝被锁死了。**
4. `_stop`（`:1091-1096`）先领取消号，再 `_settle_all("cancelled")`，最后 `interrupt()`。

交付形态复测：提问后 **0.2s** 按 ■ 停止，`awaitingSeen 0`（**从没进过**「等待审批」），0.7s `停止中` → **1.2s `已停止`**，此后 26s 轨迹全是 `已停止`。停止那一轮同样进记忆：库里 session 1 那条 `run_python {"code": "print('D7')"}` 的 `observations` ＝「用户按了停止，本次执行已取消，未产生任何副作用。」，屏上是 `⏹ 待批 · run_python · 随停止取消` + `⚪ 已取消`。**语义扩了一格**：`■ 停止` 现在覆盖"**本轮之后到达的**待批"。

**验证与回滚。** 离线 `/tmp/v15_test.py` **65 条断言全 PASS**（编解码 16 / 落库与重启 22 / D7 17 / 回归 10），其中 1n 是**拿框架自己的 `write_memory_to_messages()` 逐字比对回灌前后**，2l 断言回灌进来的都是**上一题**的 steps、本题累计边界仍从 0 起算（`300/13`），3l 端到端跑真 `_stream_response` ＋ 假 `agent.run`（0.6s 后调 gated 工具）→ 0.2s 按停止 → **3s 内自己结束**。回归项里 `outputs` 仍 7/3/4、门没有被套两层。回滚双向都演过：v1.4 方向 **15 条全 PASS**（行数 893、没有 `encode_memory`/`MEM_FMT`/memory DDL/`_run_seq`，而 D5/V5/D6 与审批闸全在），v1.5 方向 **13 条全 PASS**，恢复后与 `.rollback/v1.5/` **逐字节一致**，再跑离线 65 条仍全绿。**数据不会坏**：`memory` 表是 additive 建的，实测拿 v1.4 的代码读写 v1.5 写过的库——`load(1)` 读出 12 行不减、`save()` 正常、`memory` 表原地留着不碰，而且 v1.4 直接在那份库上**真启动过一次**（7861 `HTTP 200`、日志无 `Traceback`）。回滚重新打开的是 V6 和 D7 两件事，不是数据。

**四条边界，第一条已经造成了真后果。** ① **侧栏选中态陈旧**（v1.4 的遗留 ③）：点「＋ 新会话」之后 radio 仍保留**上一次**的 `checked`，于是"点那条**高亮着的**旧会话"＝点了一个值没变的 radio → **不触发 change** → 问题落进新会话（探测口实测 `in 2,463`、答「不记得」，数据没坏、只是进错了门）。反证是每次点击前先读 `before-checked`：它为 `0` 时一切正常。修法是 `_new_session` 把 radio 的值同步成那条新会话，纯界面层——**本轮范围外，没擅自改**，已立 **V7**（**v1.6 修掉了，见 6.3.8；顺带订正：这里那句"反证"用的是合成点击，v1.6 实测合成点击在 gradio radio 上本就不可靠，判据一律改成 CDP 真鼠标事件**）。② `_cancelled_before` 是**类级**，一个标签按停止会让**所有**在飞的待批按 `cancelled` 结算【未验证：本轮始终一次一题】，前提仍是**一次只问一题**。③ **停在待批上的那一轮**，记忆里有 `TaskStep` 而无对应 `ActionStep`——与 v1.4 的停止语义一致，不是新增缺陷。④ 审批等待时间照旧计入步骤耗时（实测 `第 1 步 · run_python · 🟢 成功 · 272.9s`，真执行约 1s），v1.3 起就是这个口径，本轮没改；要不要单列「等待时长」另立 V 单（**v1.6 立了 V8 并做完：总时长口径一字未改，旁边多一格「审批 21.0s」，见 6.3.8**）。

#### 6.3.8 v1.6：侧栏亮的那一条就是你现在问的那一条 + 审批等待单独一格（V7 + V8）

范围按工单号锁 **V7 + V8**。`my_ui.py` **1,108 → 1,205 行**（55,774 → **63,316 B**，字符 46,071 → 50,717，对 `.rollback/v1.5` 的 `diff` 净 **`+105 / −8`**）。`my_coding_agent.py` **204 行 / 8,355 B 未动**（`cmp` 与 `.rollback/v1.5`、`.rollback/v1.6` 双份一致），上游源码零改动、库 schema 零改动；审批闸的**判定**、停止的语义、三档 token 口径**一行没碰**——V8 只从闸那里多读了一个秒数。

**V7 的根因一句话：高亮和绑定是两件事。** 侧栏那条 Radio 的 `checked` 由浏览器自己的点击历史决定，而真正决定"问题落进哪条会话"的是服务端的 `self._sid`——它在 v1.5 有**三条互不回写高亮的写路径**：`_respond` 建条（`:1008`）、`_new_session` 清空（`:1073`）、`_on_load` 指到最近一条（`:1131`）。于是点「＋ 新会话」之后屏幕换成空白（绑定＝一条还不存在的新会话），radio 却仍亮着上一条；用户照着亮着的那条点＝点了一个**值没变**的 radio → gradio 不派发 `change` → 问题落进新会话。刷新页面是同一根因的另一面：绑着最近一条、侧栏**一条都不亮**。

**为什么不干脆"每帧都带 `value`"——这条是本轮实测出来的。** gradio 6.30 里**服务端 `gr.update(value=...)` 会被当成一次 `.change` 送回后端**：程序化设 `value="B"` 触发 `.change`，设 `value=None` 也原样送回一次 `None`，但两者都**不**触发 `.input`；只有用户真的点选才 `.change` / `.input` / `.select` 三件齐发。流式期间每 0.25 秒一帧，每帧带 `value` 就是**每秒两次空转事件**，而且送回的那条回调和正在流式的那条会抢同一个 chatbot 输出——抢赢就把刚画出来的步骤卡盖掉。所以方向反过来：**`choices` 每帧刷，`value` 只在绑定真的换了那一次给**，新增的 `_radio_update(force=False)`（`:968-986`）就是这一句：`force or self._sid_shown != self._sid` 才交 `value=self._sid`，同时把 `_sid_shown` 记上（`:983-985`）。`force` 专给 `_on_load`（`:1132`）——刷新后浏览器那一侧的 radio 是全新的、没勾选，服务端这个对象却还是刚才那一个、`_sid_shown` 没变，不强迫就永远不补那一下。真送回的那一次由 `_select_session` 的**回声守卫**退回（`:1111-1112`）：`if not sid or str(sid) == self._sid: return gr.update(), gr.update(), gr.update()`——三个输出全交空更新（不碰 chatbot），且守卫**挡在 `int()` 之前**，所以 `value=None` 的回声不会崩。真切换时 `_sid` 与 `_sid_shown` **一起**更新（`:1113`、`:1115`），下一帧就不会再多送一次 `value`。

**V8 的由来是 6.3.7 边界 ④ 那句白纸黑字的"本轮没改"。** `272.9s` 里 271 秒是人在等按钮，模型和工具加起来约 1 秒——把等待算进步骤耗时是 v1.3 卡片化时留下的口径，诊断上是误导：分不清到底是模型慢、工具慢，还是没人点。**总时长的定义一个字没改**（仍是框架的 `timing.duration`，含等待），只是旁边多一格可以单看的数。记账是一条跨线程的链，四个位置各有分工：

```mermaid
flowchart LR
    subgraph WR["worker 线程（工具调用侧）"]
        D1["waited 记在落定那一刻<br/>decide() my_ui.py:371<br/>超时分支 :377 记 APPROVAL_TIMEOUT"] --> D2{"ap.waited ≥<br/>APPROVAL_WAIT_MIN=0.05<br/>:40"}
        D2 -->|否| D3["不过账<br/>随停止取消的微秒级等待<br/>:590-592 之前就被筛掉"]
        D2 -->|是| D4["OpsUI._pending_wait += waited<br/>同一个 _gate_lock 临界区 :590-592"]
    end
    D4 --> U1["_stream_response 收到 ActionStep<br/>一次取干 :876-877"]
    U1 --> U2["payload._opsui_wait = waited（私有属性，不在 MEM_FIELDS :64-79）<br/>self._run_wait += waited :879-880"]
    U2 --> V1["步骤卡 22.1s · 审批 21.0s<br/>:702-708，末行「含审批」:723"]
    U2 --> V2["_stats 的 task_wait（当前会话 steps 求和）:748<br/>→ 状态条「本题审批」pill :771-772"]
    U3["开局清零 _pending_wait / _run_wait<br/>:818 / :822"] -.-> D4
```

**接进去只有四处，每一处都刻意保持小。** ① `_radio_update` 新增，三个调用点换过去：`_respond` 每帧那条从裸 `gr.update(choices=...)` 改成 `radio = self._radio_update`（`:1023`，可调用、逐帧现算）、`_new_session` 返回 `self._radio_update()`（`:1074`）、`_on_load` 返回 `force=True` 那版（`:1132`）。② 等待的**记**与**取**分在两条线程上，所以账挂在类级 `_pending_wait`（`:521`）上——和 `_run_seq` 同一个理由：门只装在进程唯一的那个 agent 上，装门的实例和画卡的实例可能不是同一个。③ 显示面三处各加一格且**都是加法**：步骤卡标题（`:708`）与正文（`:703`、`:723`）、审批卡结算后 `· 等了 X.Xs`（`:631`）、状态条 pill（`:771-772`）。④ 门槛 `APPROVAL_WAIT_MIN = 0.05`（`:40`）在**过账点**和**审批卡标题**两处生效，所以「本题审批」和「等了 X.Xs」是同一口径，不会出现 pill 上没有、卡片上写 `0.0s` 的错位——`0.05` 这个数不是拍的：D7 那条"入队即随停止取消"的路，账上确实有 0.0004 秒，加门槛之前交付形态实测抓到过 `⚪ 已取消 · 0.9s · 审批 0.0s` 这种纯噪声。

**V7 是在种子库上原地复现再复跑的**（探测口 7861，3 条会话、**零模型调用**，点击全部走 CDP `Input.dispatchMouseEvent` 真鼠标事件；证据 `/tmp/v16_base.before.txt` / `/tmp/v16_base.after.txt`）：

| 步骤 | v1.5（改之前） | v1.6（改之后） |
|---|---|---|
| 0 打开页面 | `chk=[false,false,false]`——**绑着丙却一条都不亮** | `chk=[true,false,false]`——绑谁亮谁 |
| 1 点「甲」 | `chk=[false,false,true]`，屏上 1 问 1 答 | 同（无回归） |
| 2 点「＋ 新会话」 | **`chk=[false,false,true]` 甲还亮着**，屏上已是「还没有会话」 | `chk=[false,false,false]` 全不亮，与屏一致 |
| 3 点那条亮着的「甲」 | **空点**：`chk` 不变、`user/bot` 都不出现（`change` 没派发）→ 下一问落进新会话 | `chk=[false,false,true]`，1 问 1 答回来 |
| 4 对照：点从没亮过的「乙」 | 正常 `chk=[false,true,false]` | 正常，两边一致 → **差别只在"值没变的那一次"** |

**V8 与 V7 的端到端都走交付形态 7860、真 qwen-plus**（`/tmp/v16_delivery.py` 经 CDP 9333 驱动 headless Chrome，库＝真实的 `smolagents/.agent-history.sqlite3`）：

| 判据 | 结果 |
|---|---|
| 总时长口径不变、等待单列 | 状态条 `本题耗时 22.9s` ＋ **`本题审批 21.0s`**；步骤卡 `第 1 步 · run_python · 🟢 成功 · 22.1s · 审批 21.0s · in 2,349/out 22` |
| 没审批就一格都不多 | `第 2 步 · final_answer · 🟢 成功 · 0.8s · in 2,433/out 17`——标题、正文、状态条都没有"审批 0.0s" |
| 审批卡结算后带等待 | `🟢 待批 · run_python · 已允许 · 等了 21.0s` |
| 长等待对照（探测口挂 71.0s 再点允许） | `本题耗时 72.9s` / **`本题审批 71.0s`** / `Final answer: 21`；等待期间 `本题耗时 0.0s`、状态 `等待审批`、pill `待批 run_python` |
| V7 新会话把高亮清掉 | `chk=[false,false,false]`，与屏上「还没有会话」一致 |
| V7 点那条旧的真回来了 | 点 A 会话 → `chk=[true,false,false]`、屏上 1 问 4 气泡、`Final answer: 21` |
| V7 追问落在对的那条 | 同一条再问 → `第 1 步 · final_answer · 🟢 成功 · 0.8s · in 2,525/out 17`、`Final answer: 21`；`in 2,525` 说明带着历史，侧栏**没有多出会话** |
| D7 复测（加门槛之后） | 提问后 0.9s 按 ■ 停止：从没进过「等待审批」、**2.0s 自己收尾**、`⚪ 已取消 · 1.1s`，**「审批 0.0s」那格不再出现** |
| 真模型 + 会话链（探测口 7861） | 新会话问「记住一个数字：73」→ 该条**当场点亮**、`in 2,344/out 16`；点「＋ 新会话」→ `chk` 全 false；**点回那条**（v1.5 是空点）→ `userN=1 botN=2`；追问 → **`Final answer: 73`**、`in 2,439`、进程 `4,783/33` |

**验证与回滚。** 离线 `/tmp/v16_test.py` **92 条断言全 PASS**（`FAILS: 无`）＝ v1.5 那 **65 条原样搬过来全绿**（编解码 16 / 落库与重启 22 / D7 17 / 回归 10）＋ **V7 10 条**（5b 刷新后不再是"绑着某条、一条都不亮"、5d 值没变的那次回声三个输出全空、**5g 新会话之后点"刚才那条"是真切换**、5h `value=None` 的回声不崩、5j 整题只回送一次 `value`）＋ **V8 17 条**（6a 记在 `decide()` 那一刻、6d 入队即取消不过账、6g 两格并存且后者 ≤ 前者、6l 没审批的题一格不多、6m 换题清零、**6n `_opsui_wait` 进不了记忆库**、6o 总时长照旧进得去、6p/6q 审批卡用同一条门槛）。回滚双向都演过：**v1.5 方向 25 条全 PASS**（`py_compile`、`import` 起来且字符数与磁盘一致、行数 1,108、**V7 四个锚点全不在**——含"新会话那句不回写高亮"这条 bug 本体、**V8 六个锚点全不在**、`Approval` 不记等待），**v1.6 方向 31 条全 PASS**；两份断言里 **14 条共享清单两个方向都必须绿**（V6 编解码 / memory 表 / `_bind_memory` 回灌 / 落库归属判据、D7 四个锚点、D5、V5、D6、v1.3 审批闸）→ 这两刀都是**加法式**改动。恢复后与 `.rollback/v1.6/` **逐字节一致**（`cmp` 两份），再跑离线 92 条仍全绿。**数据不会坏**：本轮没建表、没改 `MEM_FMT`、没改字段白名单，v1.6 写的 payload 与 v1.5 是**同一个格式**、回滚后照读；屏上多显示的那格等待**从来没进过库**，所以也不存在"回滚后读出多余字段"。回滚重新打开的是 V7 那个真后果和"等待看不见"，不是数据。

**四条边界。** ① **「本题审批」跨重启读不出来**：`_opsui_wait` 是 `ActionStep` 对象上的**进程内私有属性**，`MEM_FIELDS`（`:64-79`）不认它 → 回到旧会话只见「本题耗时」不见「本题审批」（6n/6o 就是这件事的两面断言，新题照旧单列）。这和 v1.5 定的"只存 `to_messages()` 读到的字段"是同一条纪律，**是写下来的边界，不是缺陷**；要让它进库得给记忆格式升 `MEM_FMT` v2 ＋ 兼容读旧 payload，已立 **V9**。② **V7 的回声守卫假设"一个窗口"**：`_select_session` 按 `str(sid) == self._sid` 拦回声，两个浏览器标签同时开着时，另一个标签的**真实**切换会被服务端当成"值没变"退回【未验证：本轮全程单标签】——与 6.3.7 边界 ② 是同一类限制，前提仍是**一次只问一题**。③ **新会话没有可亮的那一条**：点「＋ 新会话」那一刻库里还没有它的行（第一问下去才 `hist.ensure`），所以 `self._sid = None`、侧栏一条都不亮才是实话（`:1073`）；若哪天改成点击即建行，这里必须跟着改成"亮那一条"，否则又是一次高亮/绑定分家。④ **并行多工具时那一格等待挂在第一个到达的 `ActionStep` 上**（"一次取干"），多格怎么分摊【未验证：本轮所有题都是单工具】；待批队列仍只处理**最早**那一条（v1.3 起就是）。

### 6.4 `~/Desktop/我的Agent.app` + `~/Desktop/关闭Agent.command`：全链路状态机

```mermaid
stateDiagram-v2
    [*] --> 已停止
    已停止 --> 冷启动中: 双击图标
    冷启动中 --> 冷启动中: 清 Chrome 会话恢复状态（launcher:31）
    冷启动中 --> 等服务: 让 Terminal do script（launcher:104）
    等服务 --> 已停止: 40 秒内没监听就弹窗报警
    等服务 --> 运行中: 7860 起来
    运行中 --> 前置已有窗口: SingletonLock 里的 PID 仍存活（launcher:116-122）
    前置已有窗口 --> 运行中
    运行中 --> 运行中: open -n 起独立 app 窗口（launcher:127）
    运行中 --> 已停止: Ctrl-C（退出码 130）或双击关闭脚本
    已停止 --> [*]
```

关停脚本只认三样东西（`关闭Agent.command:28`、`:35`、`:39`）：7860 上命令行含 `my_ui.py` 的监听者、`agent-ui-start.sh` 的 shell、专用 profile 的 `SingletonLock`。批量收终端窗口时**把自己那一扇排除在外**（`:72`），改在脚本 exit 之后由脱离会话的 closer 延时 5 秒收（`:53`）。

四条踩出来的结论（都属于"看起来对、实际错"）：

1. `exec "$CHROME"` 会把 PID / 身份交给 Chrome，LaunchServices 于是认为你的 bundle 还活着 → 下次双击只发 reopen 事件 → Chrome 回答一个带地址栏的普通窗口。**这就是"我双击图标为什么弹出浏览器页面"的根因之一**，正解是 `exec /usr/bin/open -n -a "Google Chrome" --args --app=…`（`launcher:124-127`）。
2. 判"窗口已存在"要用 `$PROFILE/SingletonLock`，且测试符是 **`-L` 不是 `-e`**：软链的"目标"是 `主机名-PID` 字符串，永远不是真实文件，用 `-e` 恒假、守卫静默失效。
3. Chrome 认为上次没干净退出时会把会话恢复成**普通浏览器窗口**，所以每次启动前删 4 个 Session/Tabs 文件并改写 `Preferences` 的 `exit_type` / `exited_cleanly`（`launcher:28-40`）。
4. 关终端窗口的坑最深：Terminal 在"窗口里有进程在跑"时会弹「你想要终止这个窗口中正在运行的进程吗？」，点它需要**辅助访问权限**，而 Terminal 拉起的脚本拿不到（实测 `-25211 osascript 不允许辅助访问`）→ 关窗命令永远卡住。可行做法是把关窗动作 `fork + setsid` 挪出该终端会话，让那扇窗口的 shell 安静停在提示符上再 close（`launcher:44-79`）。另外 `count of windows` 会把 tab 已消失的幽灵窗口计入，**不能用它验证关没关掉**；可信判据是 `who` / `ps -t ttysNNN` + System Events 窗口数 + 未决警告数。

### 6.5 两份 HTML

`agent链路图.html`（22 KB：序列图 + 活动图 + "为什么那个窗口拒了你"对照表）与 `agent链路详解.html`（29 KB）是同一诉求的产物：**把链路可视化到能双击就看**。这两份目前是**裸 `.html`**，双击走系统默认浏览器——没有像 6.4 那样给它们套手写 bundle（`Info.plist` + `MacOS/launcher` + `Resources/app.icns`）。套外壳这件事只在 `我的Agent.app` 上真正落地并验过；对 HTML 来说它还是"下一步可做"，不要当成既有事实引用。

一条当时踩到的环境坑留在这里当线索，**但它没有在 HTML 外壳这条路上复验过**：路径含中文时 `--app=file://…` 疑似被 Chrome 静默忽略、退化成普通新标签页且不报错，需先做百分号编码；验证要看窗口标题（App 窗口标题就是文档 `<title>`，不带 `- Google Chrome` 后缀）。【待补】真给 HTML 套 App 时重新验一遍。


---

## 7 跨仓视角：同一个"读代码找答案"的请求走完四个节点

以你实测过的那题为例（"final_answer 在哪一行注册进 self.tools，把前后 3 行读出来"）：

```mermaid
sequenceDiagram
    autonumber
    participant U as 你（App 窗口输入）
    participant UI as GradioUI（gradio_ui.py:279）
    participant AG as ToolCallingAgent 循环
    participant MD as qwen-plus（云端，只做决策）
    participant TF as 工具层（本地）
    U->>UI: 提问
    UI->>AG: agent.run(task, stream=True)
    AG->>AG: 组装提示：system 含 8 个工具签名 + TaskStep
    AG->>MD: generate
    MD-->>AG: tool_call list_dir
    AG->>TF: 本地执行，云端不碰你的机器
    TF-->>AG: Observation
    AG->>MD: 回灌后再决策
    MD-->>AG: tool_call grep_files
    AG->>TF: 正则扫描，跳过 SKIP_DIRS，上限 100 命中
    TF-->>AG: smolagents/src/smolagents/agents.py:402
    AG->>MD: 回灌
    MD-->>AG: tool_call read_file 指定 start_line 与 lines
    AG->>TF: guarded() 三重校验后读文件
    TF-->>AG: 带行号片段
    MD-->>AG: final_answer
    AG-->>UI: 流式吐答案
    UI-->>U: 你看到答案（5 步，累计 input 19,399 token）
    Note over AG,TF: 若这步模型改成调 write_file，落点是 .agent-staging 且只回 diff
```

**节点归属一句话**：smolagents 站在"② 编排内核"，它调用的工具层就是 MCP 那种"① 工具层"的**进程内版本**。如果把这 5 个自写工具改写成 MCP server，② 与 ① 之间就变成跨进程协议——代码量增加一点点，可复用性从"这个应用"变成"任何宿主"。这是这套语料下一步最自然的连线。

---

## 8 BDD 场景清单（验收口径，可直接当测试用例读）

```gherkin
# 语言: 中文。功能: 本地 Agent 客户端
功能: 双击图标即开即用

  背景:
    假如 我的百炼 Key 只存在于 smolagents/.env，不出现在任何其它文件

  场景: 首次冷启动
    当 我在桌面双击「我的Agent」
    那么 Terminal 里出现服务日志，且日志中不含 "gradio.live"
    并且 监听 7860 的进程地址只有 127.0.0.1
    并且 出现一个无地址栏、无标签页的独立应用窗口，标题为 "Smolagents"

  场景: 已运行时重复双击
    假如 Agent 窗口已经打开
    当 我再次双击图标
    那么 只前置已有窗口
    并且 不产生新的 Chrome 实例，也不产生普通浏览器窗口
    并且 不触碰我日常 Chrome 的标签页与登录态

  场景: 关停
    当 我双击「关闭Agent」或在日志窗口按 Ctrl-C
    那么 7860 无监听者，且 Agent 专用 Chrome 进程数为 0
    并且 跑过启动器的那个终端窗口被自动收起
    并且 不弹出需要我手动确认的「终止正在运行的进程」警告
```

```gherkin
# 功能: Agent 的能力边界（安全）
功能: 白名单 + 校验 + 熔断，而不是模型自觉

  场景 outline: 越界一律拒绝
    当 模型请求读取 "<路径>"
    那么 结果是 <预期>

    例子:
      | 路径                     | 预期                         |
      | smolagents/my_ui.py      | 放行，返回带行号片段          |
      | smolagents/.env          | PermissionError，拒绝凭证目录 |
      | ../../其他目录/x.py      | PermissionError，越界         |
      | ~/.ssh/id_rsa            | PermissionError，越界         |

  场景: 写操作不落地
    当 模型调用 write_file 修改一个白名单内的文件
    那么 原文件内容不变
    并且 副本落在 .agent-staging 下的同名路径
    并且 返回值是 unified diff，并提示我自己执行 cp 才生效

  场景: 执行环境降级
    当 模型调用 run_python
    那么 子进程的 env 只有 PATH / HOME / PYTHONIOENCODING / PYTHONUTF8 / LANG
    并且 它拿不到 OPENAI_API_KEY
    当 代码里含 rmtree / socket / urllib / requests / subprocess
    那么 直接被正则拒绝，未执行
    当 代码运行超过 20 秒
    那么 被超时杀掉并返回"超时 20 秒，已杀掉"

  场景: 模型幻觉出不存在的工具
    当 模型调用 web_search，而我的工具表里没有它
    那么 框架抛 AgentToolExecutionError
    并且 错误文案是 "Unknown tool web_search, should be one of: ..."
    并且 这个错误被回灌成下一步输入，而不是打断整个 run

  场景: 死循环熔断
    假如 max_steps = 8
    当 模型连续 8 步交不出 final_answer
    那么 框架强制它基于已有记忆总结一次
    并且 末步标记 AgentMaxStepsError，答案被标注为不可信
```

```gherkin
# 功能: 执行前审批与步骤卡（v1.3 / P0-2 + V4）
功能: 会动东西的两只手，先给你看参数再让它动

  场景: 允许
    当 模型调用 run_python 或 write_file
    那么 会话里出现一张「🟡 待批 · 工具名」卡，参数原样贴在卡里
    并且 顶部状态条多一颗「待批」胶囊，「✔ 允许」「✖ 拒绝」被点亮
    并且 此刻磁盘上没有本工具的任何副作用——它一行都还没跑
    当 我点「✔ 允许」
    那么 工具执行，随后出现「🛠 第 N 步 · … · 🟢 成功」卡

  场景 outline: 没执行的三种说法必须分开，且两卡口径一致
    当 待批项被 <处置>
    那么 审批卡收尾成 <审批措辞>，同一步的步骤卡是 <步骤卡措辞>
    并且 交回模型的观察值写明"未产生任何副作用"
    例子:
      | 处置         | 审批措辞   | 步骤卡措辞   |
      | 点「✖ 拒绝」 | 已拒绝     | ⚪ 已拒绝     |
      | 点「■ 停止」 | 随停止取消 | ⚪ 已取消     |
      | 挂满 600 秒  | 超时未批   | ⚪ 超时未批   |

  场景: 只读工具不问
    当 模型调用 read_file / list_dir / grep_files
    那么 不出审批卡，直接执行（一次检索三连问三遍比不加还慢）

  场景: 命令行不过闸
    当 我在终端直接跑 python my_coding_agent.py 调同一只手
    那么 没有审批环节——门是 UI 装在工具实例上的，设计如此

  场景: 一步一张卡
    当 一个 step 结束
    那么 屏幕上只新增一张折叠卡，标题带工具名、结果色点、秒数与 token
    并且 卡末行的累计口径是**本题内**，与控制台 [Step N] 的进程内口径不是一回事
```

```gherkin
# 语言: 中文。功能: 会话连续与记忆隔离
功能: 一条会话就是一段连续的记忆，不是一屏消息

  场景: 同一页面连问两题不吞前一题
    假如 我没有点「＋ 新会话」
    当 我先问「请把数字 73 记住」再问「我刚才让你记住的数字是多少」
    那么 屏幕上两问两答共 4 行**都在**
    并且 历史库里这条会话有前一题的行（覆盖写喂的是完整列表）
    并且 侧栏仍然只有 1 条会话，标题是最早那题的前 28 字
    并且 第二题的 input token 比第一题多约 100（等于上一题的一问一答）

  场景: 新会话是另一段记忆，不只是新屏
    当 我点「＋ 新会话」后问同一道「我刚才让你记住的数字是多少」
    那么 模型答「不记得」
    并且 该题 input token 回到裸起步的量（实测 2,363 而非 2,464）
    并且 库里新增第 2 条会话

  场景: 点旧会话能接着聊
    当 我在侧栏点开一条旧会话再提问
    那么 屏幕换成那条会话的消息，且 sid 一并切过去
    并且 这一题落在**同一条**会话里，不是另开一条
    并且 模型答得出那条会话里 earlier 的内容（实测回 73）

  场景: 刷新页面回到最近一条
    当 我刷新页面或重开应用
    那么 侧栏按 updated_at 倒序列出会话，屏上自动展开最近有动作的那条
    并且 直接接着问不会另开一条会话
    并且 老会话一有动作就回到列表第一（v1.2~v1.3 的 WHERE 条件会漏刷，即 D6）

  场景: 停止的半截也算这一轮
    当 我在多步任务中途按「■ 停止」
    那么 已经产生的半截内容落库，且**前几轮仍在**
    并且 收尾气泡是 status=done 的「⏹ 已停止」

  场景 outline: 记忆只在进程里（v1.4 的边界，v1.5 已关掉）
    假如 服务重启过
    当 我点开重启前的旧会话接着问
    那么 屏上历史读得出来
    但 模型答「不记得」——v1.4 时 AgentMemory 不落库；v1.5 起由 memory 表回灌

  场景: 关掉再开，旧会话还记着（V6）
    假如 我用桌面的「关闭Agent」收工，再双击「我的Agent」开起来
    当 我在侧栏点回那条旧会话，问「我刚才让你记住的数字是多少」
    那么 屏上那串字是从 messages 读回来的
    并且 模型答得出 73——那是 memory 表回灌的 steps（实测该题 in 2,574，裸起步是 2,363）
    并且 工具跑过的结果一样带着：第二次重启后问「刚才 run_python 打印了什么」答 21

  场景: 持久化不等于共享（新会话照旧一无所知）
    当 我点「＋ 新会话」问同一道题
    那么 模型答「不记得」，该题 input 回到裸起步的 2,363
    并且 库里新那条会话的 memory 行从零开始，旧的一条不受影响

  场景: 半截停止的那一轮也进记忆
    当 我在多步任务中途按「■ 停止」
    那么 落库的是那一刻的 steps，下次接着聊从那一刻的进度继续
    并且 被取消的那次工具调用交回模型的是「未产生任何副作用」那句

  场景: 停止落在待批卡出现之前（D7）
    当 我在审批卡**还没画出来**的时候按「■ 停止」（实测提问后 0.2 秒）
    那么 界面走到「已停止」，不会停在「等待审批」等我补刀
    并且 随后才到达的那条待批自己按「随停止取消」结算
    并且 实测 awaitingSeen=0：状态条从没进过「等待审批」，0.7s 停止中 → 1.2s 已停止

  场景 outline: 带图的观察值不进持久记忆（已知边界）
    假如 某一步的观察值里有图片
    当 我重启后接着问那张图里是什么
    那么 模型读不到它——images / image_outputs / model_output_images 三样一律不存【未验证：本轮题面全是纯文本】

  场景: 待批与累加同屏
    当 一条已有历史的会话里出现工具审批
    那么 待批卡排在旧消息下面，旧的一条不丢
    并且 允许后步骤卡照常出「🟢 成功 · 秒 · token」

  场景: 侧栏亮的那一条就是我现在问的这条（V7）
    当 我点「＋ 新会话」
    那么 侧栏一条都不亮——这条会话此刻在库里还没有行（第一问下去才建行），亮着任何一条都是骗人的
    当 我点回刚才那条旧会话
    那么 它是真切换，屏上内容和绑定一起回来（v1.5 这里是"点了一个值没变的 radio"，change 不派发，问题落进新会话）
    当 我刷新页面
    那么 亮着的那一条就是我现在绑着的那一条（v1.5 是绑着最近一条、侧栏全部不亮）
    并且 提问时新建的会话当场点亮

  场景: 审批等待单独看得见，总时长口径不变（V8）
    假如 一条待批我隔了约 21 秒才点「允许」，工具本身跑了约 1 秒
    那么 步骤卡标题是「22.1s · 审批 21.0s」，正文「本步 22.1s（含审批 21.0s）」
    并且 状态条多一枚「本题审批 21.0s」，审批卡结算后带「已允许 · 等了 21.0s」
    并且 「本题耗时」仍是框架 `timing.duration` 量的整步时长（含等待），**定义一个字没改**
    当 这一题没有任何审批
    那么 标题、正文、状态条一处都不多出「审批 0.0s」这种噪声（门槛 `APPROVAL_WAIT_MIN = 0.05`，随「■ 停止」取消的微秒级等待也不过账）

  场景: 回到旧会话，「本题审批」这一格读不出来（已知边界 → V9）
    当 我重启后点回一条聊过的旧会话
    那么 「本题耗时」照旧读得出，「本题审批」没有
    并且 因为等待是挂在 `ActionStep` 对象上的进程内私有属性，不在 `MEM_FIELDS` 白名单里——新题照旧单列
```

上面这些的实测记录在 `迭代记录.md`：v1.3 那节是允许 / 拒绝 / 停止三条路各在线跑过一遍，副作用用 `/tmp` 落盘文件反查，**600 秒超时只有离线断言，线上没等过那么久**；v1.4 那节是连问累加、新会话隔离、点旧会话接着聊、审批与累加同屏四条在线路（探测口 7861 与交付形态 7860 各跑过），外加 53 条离线断言和「重启后答不记得」这条边界的实测；v1.5 那节就是**把那条边界关掉**的那一刀——记住 73、跨两次真重启（`in 2,574` 与 `3,091` 两次都是重启后答对）、新会话仍隔离、审批与落库同屏四条在线路跑在**交付形态 7860** 上（真 `关闭Agent.command` 收工再开），D7 用 0.2s 抢在待批之前按停止复测，外加 65 条离线断言与双向回滚演练（v1.4 方向 15 条 / v1.5 方向 13 条，恢复后逐字节一致）；v1.6 那一刀把 v1.5 留下的两条边界都收了——V7 在**种子库＋零模型调用**的探测口上把 bug **原地复现再复跑**（打开页面 `chk` 从 `[false,false,false]` 变 `[true,false,false]`、"点那条亮着的"从空点变真切换，见 6.3.8 那张 before/after 表），V8 在交付形态 7860 上实测 `22.1s · 审批 21.0s` 与 `本题审批 21.0s`，外加 **92 条离线断言**（v1.5 那 65 条原样全绿 ＋ V7 10 条 ＋ V8 17 条）与双向回滚演练（v1.5 方向 25 条 / v1.6 方向 31 条，两份共享的 14 条清单两个方向都必须绿，恢复后与 `.rollback/v1.6/` 逐字节一致）。

---

## 9 附录

### 9.1 关键代码位置总表（按"值得跳进去看"排序）

| # | 位置 | 说明 |
|---|---|---|
| 1 | `smolagents/src/smolagents/agents.py:540-611` | ReAct 主循环 + max_steps 熔断 + 错误回灌，全框架的心脏 |
| 2 | `smolagents/src/smolagents/agents.py:1453-1502` | 工具白名单校验，`Unknown tool … should be one of`（`:1467`） |
| 3 | `smolagents/src/smolagents/agents.py:402` | `tools.setdefault("final_answer", FinalAnswerTool())` |
| 4 | `smolagents/src/smolagents/tools.py:1061-1168` | `@tool`：签名 + docstring 反射成 schema，源码存进 `__source__` |
| 5 | `smolagents/src/smolagents/local_python_executor.py:1572-1667` | `FinalAnswerException` 打桩实现交卷 |
| 6 | `smolagents/src/smolagents/local_python_executor.py:855-918`、`1309-1343` | 沙箱三闸：未注册函数 / builtins / import 白名单 |
| 7 | `smolagents/src/smolagents/monitoring.py:100-117` | token 是**累计**口径，务必和单步口径分清 |
| 8 | `smolagents/src/smolagents/gradio_ui.py:422` | `launch(share=True)` 的默认值——UI 壳最大的坑 |
| 9 | `langchain4j/langchain4j/src/main/java/dev/langchain4j/service/DefaultAiServices.java:205` | `Proxy.newProxyInstance`：接口变 agent 的唯一一处魔法 |
| 10 | `langchain4j/langchain4j-core/src/main/java/dev/langchain4j/agent/tool/ToolSpecifications.java:99` | `@Tool` → `ToolSpecification`（含 JSON Schema） |
| 11 | `langchain4j/langchain4j-core/src/main/java/dev/langchain4j/rag/DefaultRetrievalAugmentor.java:169` | RAG 四阶段入口 |
| 12 | `dify/api/core/workflow/workflow_entry.py:119`、`:159`、`:208` | 工作流入口 → graphon Engine → 事件流 |
| 13 | `dify/api/core/workflow/node_factory.py:124-133` | `pkgutil.walk_packages` 扫描 + 节点自注册 |
| 14 | `dify/api/services/app_dsl_service.py:187`、`:945` | DSL 导入 / 导出：应用即 YAML |
| 15 | `dify/docker/docker-compose.yaml`（`services:` 47 / 常驻 13） | 平台真实成本 |
| 16 | `servers/src/filesystem/path-validation.ts:11-105` | 路径白名单的核心实现 |
| 17 | `servers/src/memory/index.ts:780`、`:1134` | tools / resources 注册的标准写法 |
| 18 | `servers/src/everything/index.ts:22-41` | stdio / SSE / Streamable HTTP 三传输切换 |
| 19 | `smolagents/my_coding_agent.py:36-46`、`:157-182` | 你自己的 `guarded()` 与沙箱三闸 |
| 20 | `~/Desktop/我的Agent.app/Contents/MacOS/launcher:104-127` | TCC 绕行 + Chrome app 窗口的完整写法 |
| 21 | `smolagents/src/smolagents/agents.py:545-547`、`:470`、`:754` | **中断三件套**：`interrupt()` 置 `interrupt_switch` → 只在 `while` 顶部（步边界）生效 → 下次 `run()` 开头自动清零，所以停完不用重启 |
| 22 | `smolagents/src/smolagents/agents.py:599-602` | `finally` 里还有一次 `yield`：从外面关这个生成器必然触发 `RuntimeError("generator ignored GeneratorExit")`，谁包它谁负责吃掉 |
| 23 | `smolagents/src/smolagents/gradio_ui.py:310` | `reset_agent_memory: bool = False`——同进程内记忆与 monitor **跨题累积**，这是"本题累计"和"进程累计"必须分成两档的根因 |
| 24 | `smolagents/src/smolagents/monitoring.py:108` | 控制台 `[Step N]` 的 N 是 `len(self.step_durations)`，即**进程内**；与 `agents.py:543` 每题置 1 的**本题内**步号是两把尺子 |
| 25 | `smolagents/my_ui.py:672-727` | 步骤卡把数字写进 `metadata.title` 而不是正文：gradio 折叠组收起时**正文不在 DOM 里**（v1.1 独立统计卡在 `:31-36`，v1.3 起并进这张卡） |
| 26 | `smolagents/.venv/…/gradio/chat_interface.py:265` | `ChatInterface._setup_events()` 在 `__init__` 里就跑完——**构造之后无法重接布局**，这是 v1.2 放弃 `ChatInterface` 改自建 `Blocks` 的直接原因 |
| 27 | `chat_interface.py:145`、`:371-372` | 两条实测纠正：① `save_history=True` 存的是**浏览器 localStorage**，它**能**活过服务端重启（真正的缺口是服务端没有可查的账）；② `stop_btn` 那个按钮由 `ChatInterface` 摘下来自己管，换成裸 `Blocks` 后**点了没反应** |
| 28 | `smolagents/src/smolagents/agents.py:606-608`、`:625-637` | 步数用满后**不抛异常**：`while` 循环**外**再走一次 `provide_final_answer`（`_handle_max_steps_reached`），造出的 `ActionStep` 带 `step_number=9`、`error=AgentMaxStepsError`。所以状态胶囊要认「步数用满」而不是「完成」，而 `interrupt_switch` 管不到这一步（实测撞上过：+36.74 s、+9,096 input token） |
| 29 | `smolagents/my_ui.py:30` | `DB_PATH` 按 `Path(__file__).resolve()` 定位而非 cwd：启动器 `cd smolagents` 与否都落在同一个 `.agent-history.sqlite3` |
| 30 | `smolagents/src/smolagents/tools.py:231-249` | `BaseTool.__call__` 收尾是 `self.forward(*args, **kwargs)`（`:246`）——**实例属性优先于类上的 staticmethod**，所以审批门能盖在实例上而不动上游、不动模块级 `@tool` 对象（v1.3 `_install_gate`，`my_ui.py:546-569`） |
| 31 | `smolagents/src/smolagents/agents.py:1361-1437` | `process_tool_calls`：一步里多个工具调用走 `ThreadPoolExecutor`（`:1428-1434`）。阻塞式审批因此可能一次收到多条待批，而 UI 的按钮只结算最早那条（`my_ui.py:608`）——**并行审批是已知缺口，不是漏写** |
| 32 | `.venv/…/gradio/components/chatbot.py:55` | `status: NotRequired[Literal["pending", "done"]]`。写别的值不是报错而是**整条 chatbot 输出被丢**（`ValidationError` → `ComponentProcessingError`）：D4 就是这么藏了三个版本的 |
| 33 | `smolagents/my_ui.py:785-808`、`:810-937` | 线程 + 队列的驱动骨架：`_worker` 消费 `agent.run(stream=True)`，`_stream_response` 每 `0.25s` 取一次队列。**空转轮也要扫待批队列**，否则审批卡画不出来（agent 正卡在闸上，不会有下一个事件） |
| 34 | `smolagents/my_ui.py:50-55` | `DENIED_OBSERVATION` / `DENIED_VERDICT` 两个字典**必须同步**：前者是交回模型的措辞，后者是步骤卡反查命中的色点口径，改一个就会出现「审批卡说取消、步骤卡说拒绝」 |
| 35 | `smolagents/src/smolagents/agents.py:477`、`:478-480` | `run()` 开头：`:477` 无条件把 `system_prompt` 同步进**当前那份** `self.memory`，`:478-480` 才是 `if reset: memory.reset(); monitor.reset()`。v1.4 的会话级记忆隔离**只换引用、绝不说 `reset=True`**，依据就是这两行——一 reset 连 `monitor` 一起清零，「进程累计」口径当场作废（`my_ui.py:940-965`） |
| 36 | `smolagents/src/smolagents/memory.py:214-232` | `AgentMemory` 只有 `system_prompt` + `steps` 两个字段和一个 `reset()`，**没有任何 (de)serializer**——框架不给口子，所以 v1.5 的 V6 是自己写字段（`my_ui.py:123-213`），而不是给 `AgentMemory` 加序列化器：上游升级时冲突面仍然只有 `my_ui.py` 一个文件 |
| 37 | `smolagents/src/smolagents/gradio_ui.py:310` + `:389` | `reset_agent_memory: bool = False` 的默认值声明在 `:310`，实际传参在 `:389`（`run(task, images=…, stream=True, reset=self.reset_agent_memory)`）。"记忆跨题累积"这件事是这两个位置共同决定的，v1.4 的 `base = hist.load(sid)` 与之是**两套独立的累加**（显示层 vs 模型层） |
| 38 | `smolagents/my_ui.py:1013`、`:1028` | D5 的全部修法就这两行：起点是库里那一串（`base`），每帧 `last = base + [user_msg] + list(msgs)`。`History.save()` 的覆盖语义**没改**——它只有在喂完整列表时才等价于追加，v1.3 之前喂的就是不完整的那串 |
| 39 | `smolagents/my_ui.py:1098`、`:1185`、`:1118`、`:1192` | V5 的接线：`_select_session` 交出第三个值 `int(sid)`、`radio.change` 的 `outputs` 多带 `sid`、`_on_load` 同样交出 `sid` 并挂 `demo.load`。少任一处都会退化成"屏上像接上了、其实另开一条会话" |
| 40 | `smolagents/my_ui.py:469-472` | `updated_at` 必须每次 `save()` 都刷（D6）。侧栏 `ORDER BY updated_at DESC` 决定了 `_on_load` 把 `sid` 指到哪条，也就是"下一条提问落进哪条会话"——以前挂在 `WHERE title='新会话'` 上，会话有了标题就再也不刷新 |
| 41 | `smolagents/src/smolagents/agents.py:767-769` | **V6 的全部根据**：模型读到的那一串＝`memory.system_prompt.to_messages()` ＋ 逐条 `step.to_messages()`。所以持久化要存的是 **steps 的字段**而不是屏上的卡片文字；编码在 `my_ui.py:123-154`，回灌在 `:960-962` |
| 42 | `smolagents/src/smolagents/agents.py:609-611`、`:625-637` | `memory.steps` 的**封闭集合**只有 `TaskStep` / `ActionStep` / `PlanningStep`：`FinalAnswerStep` 只 yield 不 append，步数用满时补进去的是带 `AgentMaxStepsError` 的 ActionStep。字段白名单 `MEM_FIELDS`（`my_ui.py:64-79`）就是照这个集合列的 |
| 43 | `smolagents/src/smolagents/utils.py:146-153` | `make_json_serializable` 会把**长得像 JSON 的字符串解析成 dict**。记忆编码里只有 `action_output` 过它，其余文本原样存，否则观察值 `{"ok": true, "n": 73}` 回放回来就变字了 |
| 44 | `smolagents/src/smolagents/agents.py:470` | **D7 的根因**：每次 `run()` 开头把 `interrupt_switch` 清回 `False`。所以「■ 停止」落在待批卡出现之前，中断的是**空闲的** agent（空放），后到的待批没人结算。修法不在上游这一行，在 `my_ui.py:583-586` 那个临界区 |
| 45 | `smolagents/my_ui.py:516-517`、`:824-825`、`:1091-1096` | 取消号三件套：**类级** `_run_seq` / `_cancelled_before`（闸装在进程唯一的那个 agent 上，号必须和 `_pending`、`_gate_lock` 同侧）、起 worker 之前先领本轮号、`_stop` 先领取消号。入队与判停必须**在同一个 `with` 里**，分开写窗口就还开着 |
| 46 | `smolagents/my_ui.py:1064-1065` | 记忆落库的两个条件：`mem is not None` 且 `self._mem_sid == sid`。后一条是**会话归属**判据——中途换了会话还照存，就把别人的记忆盖到这条上了 |
| 47 | `smolagents/my_ui.py:968-986` + `:1111-1112` | **V7 的全部根据是一条实测的 gradio 6.30 语义**：服务端 `gr.update(value=...)` **会被当成一次 `.change` 送回后端**（设 `None` 也送回 `None`），但 `.input` / `.select` 都不触发；只有用户真点选才三件齐发。所以 `choices` 每帧刷、`value` 只在绑定真换那一次给（`:983-985`），送回的那次由 `_select_session` 的回声守卫三个输出全交空更新（守卫必须挡在 `int()` 之前，否则 `None` 崩）。不这么写就是每秒两次空转事件 ＋ 和流式那条抢同一个 chatbot 输出 |
| 48 | `smolagents/my_ui.py:371`、`:590-592`、`:876-880`、`:40` | **V8：一次等待跨两条线程**。记在 `decide()` 那一刻（不是 worker 醒来那刻，否则审批卡第一次画收尾态带不上这个数、超时路径也记不准）→ 类级 `_pending_wait` 过账（门槛 `APPROVAL_WAIT_MIN=0.05` 在此，与审批卡标题同一口径）→ UI 线程在 `ActionStep` 到达时**一次取干**、写 step 的私有属性 `_opsui_wait`。**它不在 `MEM_FIELDS`（`:64-79`）里**，所以总时长口径不变、重启后这一格读不出（→ V9） |

### 9.2 术语中英对照（读上游文档时不会被绕晕）

| 中文 | 英文 | 在这套语料里的对应物 |
|---|---|---|
| 编排内核 | agent runtime / loop | smolagents `MultiStepAgent`；langchain4j `AiServices` |
| 动作空间 | action space | 实测 `len(agent.tools) == 8`：你自己声明 **7** 项，`final_answer` 由 `agents.py:402` 自动补第 8 项。两套口径到处都用，**写文档时必须说明是哪一个**（本 README 的"7 只手"指你自己写/挂的那 7 项，"8 项动作空间"指模型实际能调的注册表） |
| 熔断 | max_steps guardrail | `agents.py:545` + `:625` |
| 沙箱 | execution sandbox | `LocalPythonExecutor` / E2B / dify `sandbox` / `agent_backend`+Landlock |
| 工具规范 | tool specification / schema | `ToolSpecification` / smolagents `Tool.inputs` / MCP `inputSchema` |
| 观测回灌 | observation feedback | `ActionStep.to_messages`，含 error 分支 |
| 上下文膨胀 | context / token growth | `Monitor.total_input_token_count`（累计）vs `ActionStep.token_usage`（单步） |
| 检索增强 | RAG | langchain4j 四阶段 / dify `core/rag` |
| 协议化复用 | protocol-level reuse | MCP server 进程 |
| 可观测 | tracing / observability | dify `core/ops`、OpenTelemetry |

### 9.3 复现命令清单（都是本机验证过的）

```bash
# 1) 直接命令行跑合并后的 agent（8 项动作空间）
cd ~/Desktop/study/ai学习/smolagents && .venv/bin/python my_agent.py

# 2) 起 UI（务必 share=False）
.venv/bin/python my_ui.py            # 然后浏览器打开 http://127.0.0.1:7860

# 3) 桌面方式：双击 ~/Desktop/我的Agent.app；关停：双击 ~/Desktop/关闭Agent.command

# 4) 四项验收（关窗一定用这四个，别用 Terminal 的 count of windows）
lsof -nP -iTCP:7860 -sTCP:LISTEN                              # 只应出现 127.0.0.1
who | awk '{print $2}'                                        # 会话 = 活着的终端
/usr/bin/osascript -e 'tell application "System Events" to tell process "Terminal" to count of windows'
tail -40 ~/Desktop/study/ai学习/.agent-ui.log                 # 不应出现 gradio.live

# 5) langchain4j：先切 JDK 17，再离线编一个模块
#    jdk17 来自 ~/.zshrc:111，mvn39 来自 ~/.zshrc:113
cd ~/Desktop/study/ai学习/langchain4j && jdk17 && ~/tools/apache-maven-3.9.16/bin/mvn -pl langchain4j-core -am -o compile

# 6) MCP servers（要装才跑，装之前想清楚）
cd ~/Desktop/study/ai学习/servers && npm ci && npm run build   # 注意 memory 要求 Node >= 24，本机 v22.20

# 7) dify（未部署；前置三件：cp .env、填 SECRET_KEY、确认 Docker VM 在跑）
cd ~/Desktop/study/ai学习/dify/docker && cp .env.example .env && docker info

# 8) v1.5：看记忆是不是真落了库（payload 是整份 steps，一条会话一行）
sqlite3 ~/Desktop/study/ai学习/smolagents/.agent-history.sqlite3 \
  "SELECT session_id, length(payload), updated_at FROM memory ORDER BY session_id;"
#    想看内容：把 payload 交给 python 解析，第一层是 {"fmt":"v1","steps":[…]}
#    回灌没生效的判据是「重启后同一题的 in 回到裸起步 2,363」，肉眼看 token 最快

# 9) 复跑本轮验收（注意：这些脚本在 /tmp，macOS 一重启就没，见 9.4 第 12 条）
python3 /tmp/v15_test.py                # 离线 65 条断言（venv python，agent.run 打桩、临时库）
python3 /tmp/v15_rollback_check.py v14  # 回滚方向断言；v15 方向同理，须先 cp 对应 .rollback 存档
node /tmp/v15_drive.js                  # CDP 驱动 headless Chrome 跑在线路，需另起 9333 端口
```

### 9.4 待补清单（我确实没验的，别当结论用）

1. 【待补】langchain4j 在本机首次编译的真实耗时与失败点（依赖是否需要联网）。
2. 【待补】dify 部署后的实际常驻容器数与内存占用（按 4.2 推算约 16 个，未实测）。
3. 【待补】MCP servers `npm ci` 之后的体积与 `everything` server 在本机的握手测试。
4. 【待补】smolagents `CodeAgent`（P1 那步）在你机器上的实际执行链与 token 曲线——目前只跑过 `ToolCallingAgent`。
5. 【待补】4.4 里 dify 迭代/并行节点的**具体** handler 类名与行号（我只确认了 `workflow_entry.py:48-49` 有容器 handler 的导入，未逐个下钻）。
6. 【待补】5.4 的协议版本号在你这份 HEAD 上确切是哪两个（`server/discover` 那条来自代码注释，未跑握手验证）。
7. 【待补】你 6.2 说的 2,375 → 19,399 是同题两配置的对比，严格口径应补一次"同题同步骤"的 A/B。
8. 【待补】v1.3 自己也有三项没实测到：一步多工具**并行审批**（按钮只结算最早那条）、**线上 600 秒超时**、`PlanningStep` 那张 🧭 计划卡。细节见 6.3.5 末段与 `迭代记录.md` v1.3 的遗留清单。
9. 【v1.4 那两项已由 v1.5 收掉，只剩一条】记忆持久化（V6）在**交付形态 7860** 上跨**两次真重启**实测（`in 2,574` 答 73、二次重启 `in 3,091` 答 21，见 6.3.7）；D7 也在交付形态复测过（0.2s 抢在待批卡之前按停止 → 1.2s 到「已停止」，v1.4 同一路死停 142.4s）。**仍然没验的**只有「线上真等满 `APPROVAL_TIMEOUT = 600` 秒会怎样」——两个端点测过（0.7s 自解、142.4s 手动补刀），中间那条超时分支只有离线断言。
10. 【待补】v1.4 的累加只测到**三问一答**的规模（`in 2,362 → 2,464 → 2,564`，每题约 +100）。十几问、或中间夹多步工具调用之后 `in` 的增长曲线、以及它什么时候开始挤到上下文上限，**没有数据**。
11. 【待补】v1.5 的三项：**多图会话的持久化**（`images` / `image_outputs` / `model_output_images` 一律不存，所以带图的观察值重启后模型读不到，而本轮题面全是纯文本）；**并发提问下类级取消号的后果**（一个标签按「■ 停止」会让**所有**在飞的待批按 `cancelled` 结算，本轮始终一次一题）；`memory.payload` 随会话变长的体积与 `in` 曲线（只测到 15 步 / 4,042 字符）。
12. 【待补·等你点头】v1.0~v1.6 七轮的验收脚本全在 `/tmp`（`v16_test.py`、`v16_cdp.js`、`v16_delivery.py`、`v16_rollback_check.py`、`v15_test.py`、`v15_drive.js` 等）——**macOS 一重启这些"复跑命令"就失效**，只剩 `迭代记录.md` 里贴的输出。要不要在 `ai学习/` 下开一个 `验收脚本/` 目录按版本号收进来，属于你的决定（新增目录，不落在任何一张工单里）。
13. 【待补】v1.6 的两项：**一步多工具并行时那一格等待怎么分**（"一次取干"把它挂在**第一个到达**的 `ActionStep` 上，本轮所有题都是单工具）；**两个浏览器标签同时开着时 V7 的回声守卫**（按 `str(sid) == self._sid` 拦回声，另一个标签的**真实**切换会被服务端当成"值没变"退回，本轮全程单标签）。另有一条**写下来的边界**不是待补：「本题审批」跨重启读不出来（`_opsui_wait` 不进 `MEM_FIELDS`），要收它得升 `MEM_FMT` v2，已立 **V9**。

### 9.5 这套语料的三条下一步（只列，不动代码）

- **P0**：把 `my_coding_agent.py` 的 5 个工具改写成 1 个 MCP server（`src/` 加一个目录，照 `filesystem/server.ts` 的 `createServer()` 骨架），验证"协议复用"这件事——同一份工具，smolagents 和 Qoder 都能调。
- **P1**：把 `my_agent.py` 换成 `CodeAgent`，对比同一个五步任务在"JSON 工具调用"与"写代码"两种动作空间下的步数与 token。
- **P2**：读 `dify/api/core/workflow/nodes/agent_v2`，看平台是怎么把"agent 节点"塞进确定性 DAG 的——这正好回答"自动循环 vs 可控流程"这个你反复问的取舍。
