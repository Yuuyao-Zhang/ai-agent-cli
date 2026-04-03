# AI Assistant - 生产级 Agentic AI 框架

> 模块化、零依赖、生产级的 AI Agent 框架，支持分层记忆、层级 RAG 知识检索、蜂群智能、状态管理、渐进式技能系统、MCP 协议等特性。

---

## 功能概览

本项目是一个**生产级的 Agentic AI 框架**，能够帮你构建具备以下能力的智能助手：

- **智能对话**：基于 ReAct 循环的多轮交互，支持思考-行动-观察的完整链路
- **知识问答**：基于层级 RAG 的知识检索，自动引用知识来源，支持 Markdown 文档管理
- **代码助手**：解释代码、分析架构、查找文件、执行命令、编辑代码
- **任务规划**：自动分解复杂任务，管理任务生命周期，支持撤销重做
- **团队协作**：蜂群智能实现多 Agent 并行协作，Map-Reduce 任务处理
- **技能扩展**：渐进式披露技能系统，支持自动召回和显式调用
- **工具集成**：统一调用本地工具和远程 MCP Server 工具
- **状态管理**：支持会话快照、分支管理、中断恢复，像 Git 一样管理工作流

---

## 快速开始

### 环境配置

设置必需的环境变量：

```powershell
# Windows PowerShell
[System.Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "你的通义千问 API Key", "User")
[System.Environment]::SetEnvironmentVariable("LLM_MODEL", "qwen-plus", "User")
```

### 启动程序

```bash
# 交互模式
python main.py

# 单次任务模式
python main.py "你的任务描述"
```

### 交互示例

```text
$ python main.py

╔══════════════════════════════════════════════════════╗
║                    AI Assistant                      ║
╚══════════════════════════════════════════════════════╝

# 查看可用技能
> skills

# 同步知识库
> kn
> 选择 6. Sync Default Knowledge Directory

# 使用技能解释代码
> /explain-code main.py

# 直接提问（自动召回知识）
> Python 默认参数 exponent=2 是什么意思
```

### 交互命令参考

| 命令 | 说明 |
|-----|------|
| `q` / `quit` | 退出程序 |
| `skills` | 显示所有可用 Skills |
| `tools` | 显示所有可用工具 |
| `kn` | 知识管理菜单 |
| `config` | 配置管理菜单 |
| `cp` | 快照管理菜单 |
| `br` | 分支管理菜单 |
| `swarm` | 执行蜂群任务 |
| `/skill-name` | 显式调用技能，如 `/explain-code main.py` |

### 自定义知识库

将 Markdown/TXT 文件放到 `knowledge/library` 目录：

```text
knowledge/
└── library/
    └── python_basics/
        ├── python_base.md
        └── python_advanced.md
```

然后在交互界面执行 `kn` → `6` 同步知识库。

### MCP Server 配置

在 `agent_config.yaml` 中添加 MCP Server：

```yaml
mcpServers:
  baidu-maps:
    url: https://mcp.map.baidu.com/mcp?ak=${BAIDU_MAPS_MCP_AK}
```

启动时自动连接并注册远程工具。

---

## 核心特性

### 特性总览

| 特性 | 说明 |
|-----|------|
| **零依赖** | 仅使用 Python 标准库，无需 LangChain 等重型框架 |
| **分层记忆** | 短期(活跃窗口) → 中期(SQLite摘要) → 长期(向量索引) |
| **层级 RAG** | 按 Markdown 标题解析 section/chunk 父子结构，精准检索 |
| **状态管理** | Git 风格的分支管理、快照保存、中断恢复 |
| **蜂群智能** | Map-Reduce 任务分解、DAG 调度、多角色协作 |
| **渐进式技能** | 四级披露机制(BRIEF→SUMMARY→DETAILED→FULL)，上下文感知 |
| **MCP 协议** | 统一调用本地工具和远程 MCP Server 工具 |
| **安全系统** | 2D ACL 权限矩阵、风险评分、HITL 人工确认 |

### 分层记忆系统

- **滑动窗口摘要**：自动压缩历史对话，保留关键信息
- **Token 预测器**：基于历史消耗预测未来 Token 需求
- **智能检索**：查询重写、多路召回、重排序优化

### 层级 RAG 知识检索

- **父子检索**：先召回标题章节，再过滤并重排子块
- **结果去噪**：标题重叠加权、代码块降权、目录节点过滤
- **来源引用**：最终回答自动附带知识来源引用

### 渐进式披露技能系统

- **自动/显式调用**：支持自动召回与 `/skill-name` 显式调用
- **热重载**：文件变更自动重载，无需重启
- **语义检索**：向量索引支持技能语义搜索
- **Anthropic 风格**：支持 `.my_agent/skills/<skill-name>/SKILL.md`

### 蜂群智能协作

- **Map-Reduce 模式**：任务分解 → 并行执行 → 结果聚合
- **多角色协作**：Worker/Manager/Critic 三种 Agent 角色
- **共识策略**：MapReduce/Voting/BestOfN 多种结果聚合策略

### 状态快照与分支管理

- **Checkpoint 快照**：支持任意时刻的状态保存与中断恢复
- **分支管理**：Git 风格的多线探索，支持分支切换与合并
- **会话隔离**：Namespace 变量隔离与继承机制

---

## 系统架构

### 设计原则

1. **模块化**：清晰的模块边界，职责分离
2. **零依赖**：LLM 调用仅使用 Python 标准库
3. **可扩展**：Hook 系统 + 插件化设计
4. **生产级**：容错机制、日志、配置管理

### 数据流架构

```
用户输入
    ↓
IntentRecognizer (意图识别)
    ↓
ContextAssembler (Token 预算分配)
    ↓
UnifiedMemoryManager (短中长期记忆检索)
    ↓
KnowledgeManager (层级 RAG 检索 + 来源引用)
    ↓
SkillManager (技能召回与渐进式披露)
    ↓
LLM API Call
    ↓
Parser (指令解析)
    ↓
SecurityManager (权限检查)
    ↓
Tools (工具执行)
    ↓
Session (状态更新)
    ↓
输出结果
```

### 记忆架构

```
┌─────────────────────────────────────────────────────┐
│                  Context Window                      │
│  ┌───────────────────────────────────────────────┐  │
│  │  System Prompt + Dynamic Context              │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  Short Term (Active Window)                   │  │
│  │  - 最近 N 轮完整对话                          │  │
│  └───────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────┐  │
│  │  Mid Term (SQLite)                            │  │
│  │  - 会话摘要                                   │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
┌─────────────────────────────────────────────────────┐
│  Long Term (Vector DB + Raw Logs)                   │
│  - 向量化存储                                       │
│  - 原始日志                                         │
└─────────────────────────────────────────────────────┘
```

### 项目结构

```text
.
├── engine/             # 核心引擎
│   ├── agent.py        # Agent 主循环，集成所有组件
│   ├── tools.py        # 工具执行 (bash/read/write/edit/todo/grep/glob/tool)
│   └── hooks.py        # AOP Hook 系统
├── llm/                # LLM 接口
│   ├── llm.py          # 通义千问调用，零依赖实现
│   ├── context.py      # 上下文组装器，Token 预算管理
│   ├── parser.py       # 指令解析
│   ├── intent.py       # 意图识别模块
│   └── terminal.py     # 终端输出捕获
├── memory/             # 分层记忆系统
│   ├── unified_manager.py  # 统一记忆管理器
│   ├── stores/         # 三层存储 (短期/中期/长期)
│   ├── retriever/      # RAG 检索 (重写/召回/重排)
│   └── vector/         # 向量处理
├── state/              # 状态管理
│   ├── session.py      # 会话状态，支持 fork 和快照
│   ├── manager.py      # 任务生命周期管理
│   ├── checkpoint.py   # 状态快照
│   └── branch.py       # 分支管理
├── swarm/              # 蜂群智能
│   ├── planner.py      # MapReduce 任务分解
│   ├── scheduler.py    # DAG 任务调度
│   └── consensus.py    # 结果共识
├── skill/              # 技能系统
│   ├── manager.py      # 技能管理 + 渐进式披露引擎
│   ├── loader.py       # 技能加载/写入
│   └── vector_index.py # 技能向量索引
├── knowledge/          # 知识管理
│   ├── manager.py      # 知识索引与检索
│   └── vector_db.py    # 向量数据库
├── mcp/                # MCP 协议
│   ├── registry.py     # 工具注册中心
│   └── client.py       # MCP Server 客户端
├── todo/               # 任务规划
├── common/             # 通用组件
└── main.py             # 主入口
```

---

## 竞争优势

### 横向对比

| 对比项 | 本项目 | LangChain/LangGraph | 其他轻量框架 |
|-------|-------|-------------------|------------|
| 依赖 | 零依赖，标准库实现 | 依赖众多 | 部分依赖 |
| 可控性 | 完全可控，代码透明 | 黑盒封装 | 中等 |
| 记忆系统 | 三层分层记忆 | 基础记忆 | 简单记忆 |
| RAG | 层级 RAG，父子检索 | 基础 RAG | 基础 RAG |
| 状态管理 | Git 风格分支快照 | 有限支持 | 无 |
| 技能系统 | 渐进式披露 | 无 | 简单技能 |
| 蜂群智能 | Map-Reduce + DAG | 复杂工作流 | 无 |
| 生产级 | 完整安全、日志、配置 | 需自行组装 | 不完整 |

### 技术优势

1. **完全可控**：不依赖重型框架，每一行代码都可理解和定制
2. **模块化设计**：各模块可独立使用，也可组合成复杂系统
3. **生产就绪**：内置安全策略、权限控制、风险评分、人工确认
4. **易于扩展**：Hook 系统支持 AOP 编程，可在关键节点注入自定义逻辑
5. **知识友好**：层级 RAG 精准定位知识，自动引用来源

---

## 配置说明

### 环境变量

| 环境变量 | 说明 | 映射配置 |
|---------|------|---------|
| `DASHSCOPE_API_KEY` | 用于主对话模型和 embedding | `llm.api_key` |
| `LLM_MODEL` | 指定使用的模型 | `llm.model` |
| `DEBUG` | 开启调试模式 | `app.debug_mode` |
| `LOG_LEVEL` | 指定日志级别 | `app.log_level` |
| `BAIDU_MAPS_MCP_AK` | 供 MCP Server URL 展开使用 | - |

### 配置文件 (agent_config.yaml)

```yaml
llm:
  api_key: null
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
  temperature: 0.7
  max_retries: 3
  timeout: 60

context:
  system_ratio: 0.2
  history_ratio: 0.6
  file_tree_ratio: 0.05
  terminal_ratio: 0.05
  dynamic_ratio: 0.1

app:
  debug_mode: false
  log_level: INFO
  checkpoint_dir: checkpoints
  vector_db_dir: vectordb
  max_recursion_depth: 10
  max_turns_per_agent: 20

mcpServers:
  example-server:
    url: http://localhost:8000/mcp
```

---

## 设计理念

> "Simple, Modular, Production-Ready." - 简单、模块化、生产就绪

本项目致力于提供一个**不依赖重型框架**、**完全可控**、**易于理解和扩展**的 AI Agent 基础框架。每个模块都可以独立使用，也可以组合成复杂的 Agent 系统。
