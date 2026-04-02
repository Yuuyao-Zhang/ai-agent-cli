# AI Assistant - 生产级 Agentic AI 框架

> 模块化、零依赖、生产级的 AI Agent 框架，支持分层记忆、层级 RAG 知识检索、蜂群智能、状态管理、渐进式技能系统、MCP 协议等特性。

本项目是一个**生产级的 Agentic AI 框架**，采用模块化架构设计，使用 Python 标准库实现完整的 Agent 能力，无需依赖 LangChain 等重型框架。核心特性包括**分层记忆系统**、**层级 RAG 知识库**、**状态快照与分支管理**、**渐进式披露技能系统**、**MCP 协议集成**、**蜂群智能协作**等。

---

## 核心特性

### 1. 核心 Agent 引擎
- **ReAct 循环**: 思考-行动-观察循环，支持多轮交互
- **递归任务执行**: 支持子任务分解与递归调用，深度可控
- **Hook 系统**: AOP 编程模型，支持在关键节点注入自定义逻辑
- **动态上下文管理**: Token 预算分配与智能裁剪
- **意图识别**: 自动识别用户意图，支持任务分类和路由

### 2. 分层记忆系统 (Hierarchical Memory)
- **三层记忆架构**: 短期记忆(活跃窗口) → 中期记忆(SQLite摘要) → 长期记忆(向量索引)
- **滑动窗口摘要**: 自动压缩历史对话，保留关键信息
- **Token 预测器**: 基于历史消耗预测未来 Token 需求
- **上下文剪枝**: 结合摘要与活跃窗口控制 Prompt 大小
- **智能检索**: 查询重写、多路召回、重排序优化

### 3. 状态管理 (State Management)
- **会话隔离**: Namespace 变量隔离与继承机制
- **任务生命周期**: 完整的任务状态机 (创建/启动/暂停/恢复/终止/完成)
- **调用栈追踪**: 完整记录任务调用链
- **Checkpoint 快照**: 支持任意时刻的状态保存与中断恢复
- **分支管理**: Git 风格的多线探索，支持分支切换与合并

### 4. 蜂群智能 (Swarm Intelligence)
- **Map-Reduce 模式**: 任务分解 → 并行执行 → 结果聚合
- **DAG 调度**: 支持任务依赖关系的智能调度
- **多角色协作**: Worker/Manager/Critic 三种 Agent 角色
- **线程池执行**: 可配置的并发执行能力
- **共识策略**: 多种结果聚合策略 (MapReduce/Voting/BestOfN)

### 5. 渐进式披露技能系统 (Progressive Disclosure)
- **四级披露机制**: BRIEF → SUMMARY → DETAILED → FULL
- **上下文感知**: 根据用户查询智能调整信息披露级别
- **依赖管理**: DAG 拓扑排序，自动解析技能依赖
- **热重载**: 文件变更自动重载，无需重启
- **语义检索**: 向量索引支持技能语义搜索
- **Anthropic 风格目录技能**: 支持 `.my_agent/skills/<skill-name>/SKILL.md`
- **自动/显式调用**: 支持自动召回与 `/skill-name 参数` 显式调用
- **Frontmatter 配置**: 支持 `description`、`allowed-tools`、`disable-model-invocation`、`user-invocable`、`paths`
- **配套文件**: 支持 skill 目录内引用 `reference.md` 等补充材料

### 6. 安全系统 (Security)
- **2D ACL 矩阵**: 角色 × 工具 的细粒度权限控制
- **三级角色**: admin / user / guest
- **风险评分**: 0-10 级评分 + 歧义加权因子
- **HITL 确认**: 高风险操作人工确认机制
- **敏感操作检测**: 危险命令正则匹配
- **敏感路径保护**: 系统关键目录访问控制
- **路径验证**: 防止目录遍历攻击

### 7. 知识管理 (Knowledge Management)
- **自动同步**: `knowledge/library` 下的 `.md` / `.txt` 文件可一键同步
- **层级 RAG**: 按 Markdown 标题解析 section/chunk 父子结构
- **父子检索**: 先召回标题章节，再过滤并重排子块
- **结果去噪**: 标题重叠加权、代码块降权、目录节点过滤、同 section 去重
- **回答引用**: 最终回答会自动附带知识来源引用
- **向量数据库**: 基于 TF-IDF 的轻量级向量存储

### 8. MCP 协议集成
- **动态工具发现**: 自动发现 MCP Server 提供的工具
- **多 Server 支持**: 可同时连接多个 MCP Server
- **路由策略**: FIRST_AVAILABLE / ROUND_ROBIN / RANDOM
- **统一接口**: 本地工具与远程 MCP 工具统一调用
- **工具注册中心**: 集中管理所有可用工具

### 9. 任务规划 (Todo System)
- **状态管理**: PENDING/IN_PROGRESS/COMPLETED/FAILED/SKIPPED
- **版本历史**: 支持撤销/重做，最多保留10个快照
- **可视化渲染**: 美观的终端输出格式
- **批量更新**: 支持批量添加和更新任务

### 10. 工具系统 (Tools)
- **Bash 执行**: 安全的命令执行，支持超时和危险命令检测
- **文件操作**: 读(read)、写(write)、编辑(edit)文件
- **代码搜索**: 基于 Grep 的代码搜索能力
- **文件查找**: 基于 Glob 的文件模式匹配
- **MCP 工具**: 统一的 MCP 工具调用接口
- **To-do 管理**: 任务列表的增删改查

---

## 项目结构

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
│   │   ├── short_term.py   # 短期记忆存储
│   │   ├── mid_term.py     # 中期记忆存储 (SQLite)
│   │   └── long_term.py    # 长期记忆存储 (向量索引)
│   ├── retriever/      # RAG 检索 (重写/召回/重排)
│   │   ├── rewriter.py     # 查询重写
│   │   ├── engine.py       # 检索引擎
│   │   ├── reranker.py     # 重排序
│   │   └── trigger.py      # 触发器
│   └── vector/         # 向量处理
├── state/              # 状态管理
│   ├── session.py      # 会话状态，支持 fork 和快照
│   ├── manager.py      # 任务生命周期管理
│   ├── task.py         # 任务状态定义
│   ├── namespace.py    # 变量命名空间
│   ├── checkpoint.py   # 状态快照
│   ├── branch.py       # 分支管理
│   └── channel.py      # 状态通道
├── swarm/              # 蜂群智能
│   ├── planner.py      # MapReduce 任务分解
│   ├── scheduler.py    # DAG 任务调度
│   ├── factory.py      # Agent 工厂
│   ├── consensus.py    # 结果共识
│   └── types.py        # 类型定义
├── skill/              # 技能系统
│   ├── types.py        # 技能类型定义
│   ├── manager.py      # 技能管理 + 渐进式披露引擎
│   ├── loader.py       # 技能加载/写入
│   └── vector_index.py # 技能向量索引
├── .my_agent/skills/   # Anthropic 风格技能目录
│   └── explain-code/
│       ├── SKILL.md
│       └── reference.md
├── knowledge/          # 知识管理
│   ├── manager.py      # 知识索引与检索
│   └── vector_db.py    # 向量数据库
├── mcp/                # MCP 协议
│   ├── registry.py     # 工具注册中心
│   └── client.py       # MCP Server 客户端
├── todo/               # 任务规划
│   ├── store.py        # Todo 存储与版本控制
│   └── render.py       # 可视化渲染
├── common/             # 通用组件
│   ├── config.py       # 统一配置管理 (支持 YAML + 环境变量)
│   ├── security.py     # 安全策略与 ACL
│   ├── logger.py       # 日志系统
│   ├── constant.py     # 不可变核心常量
│   ├── io_utils.py     # IO 工具 (颜色、输入输出封装)
│   ├── file_lock.py    # 文件锁
│   ├── file_index.py   # 文件索引
│   └── vector/         # 向量工具
│       ├── tokenizer.py   # 分词器
│       └── similarity.py  # 相似度计算
└── main.py             # 主入口
```

---

## 快速开始

### 1. 配置系统环境变量

首次启动前，建议先写入最常用的环境变量：

- `DASHSCOPE_API_KEY`：必需，用于主对话模型和 embedding
- `LLM_MODEL`：可选，覆盖默认模型
- `BAIDU_MAPS_MCP_AK`：可选，仅在配置百度地图 MCP 时需要

Windows PowerShell 示例：

```powershell
[System.Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "你的通义千问 API Key", "User")
[System.Environment]::SetEnvironmentVariable("LLM_MODEL", "qwen-plus", "User")
[System.Environment]::SetEnvironmentVariable("BAIDU_MAPS_MCP_AK", "你的百度地图 AK", "User")
```

设置完成后，请重新打开终端让新环境变量生效。更多变量说明见「配置 > 环境变量」。

### 2. 启动 Agent

```bash
python main.py
```

支持单次任务执行模式：
```bash
python main.py "你的任务描述"
```

### 3. 首次同步知识库

将你的 Markdown/TXT 知识文件放到 `knowledge/library` 下，例如：

```text
knowledge/
└── library/
    └── python_basics/
        ├── python_base.md
        └── python_advanced.md
```

进入交互界面后，使用 `kn` 菜单同步默认知识目录。

### 4. CLI 快速体验

下面是一个启动 `main.py` 后的精简体验示例，覆盖知识同步、skill 查看和普通提问：

```text
$ python main.py

╔══════════════════════════════════════════════════════╗
║                    AI Assistant                        ║
╚══════════════════════════════════════════════════════╝

[INFO] 正在初始化 AI Agent...
[INFO] 特性: 知识管理, Skill 系统, MCP 工具, 配置文件, 日志系统, 分层记忆, 快照回溯, 分支管理, 蜂群智能

用户 (kn知识, config配置, cp快照, br分支, mem记忆, skills技能, tools工具, hooks钩子, connect连接, swarm蜂群, q退出)> skills

[可用技能]:
  - explain-code [Anthropic | 自动/手动]: 解释代码、架构和执行流程；当用户要求「讲解这段代码」「分析模块职责」「说明调用链」时使用。

用户 (kn知识, config配置, cp快照, br分支, mem记忆, skills技能, tools工具, hooks钩子, connect连接, swarm蜂群, q退出)> kn

[Knowledge Menu]
Default Knowledge Dir: G:\PythonProject\AI-agent-CLI\knowledge\library
1. Search Knowledge
2. Index File
3. Index Directory
4. List All Knowledge
5. Add Custom Knowledge
6. Sync Default Knowledge Directory
Select option (1-6): 6

[INFO] Synced knowledge directory: indexed=0, updated=0, removed=0, skipped=2

用户 (kn知识, config配置, cp快照, br分支, mem记忆, skills技能, tools工具, hooks钩子, connect连接, swarm蜂群, q退出)> /explain-code main.py

============================================================
FINAL RESULT:
`main.py` 是整个项目的命令行主入口，负责初始化 Agent、连接 MCP、注册命令菜单，并把用户输入分发到主执行循环。

技能上下文引用:
- explain-code
============================================================

用户 (kn知识, config配置, cp快照, br分支, mem记忆, skills技能, tools工具, hooks钩子, connect连接, swarm蜂群, q退出)> Python 默认参数 exponent=2 是什么意思

============================================================
FINAL RESULT:
在 Python 中，`exponent=2` 是函数定义中的默认参数，表示调用函数时如果没有显式传入 `exponent`，就自动使用值 `2`。

例如：
def power(base, exponent=2):
    return base ** exponent

- power(5) 等价于 power(5, 2)
- power(5, 3) 会覆盖默认值

知识来源引用:
- python_base.md | python_base > Python 基础 > Python 函数基础 | Chunk 2/3
============================================================
```

你也可以继续提问更复杂的知识问题，例如「Python 描述符协议是做什么的」，系统会优先命中对应标题章节，再从该章节下召回最相关的子块。

---

## 架构设计

### 核心设计原则

1. **模块化**: 清晰的模块边界，职责分离
2. **零依赖**: LLM 调用仅使用 Python 标准库
3. **可扩展**: Hook 系统 + 插件化设计
4. **生产级**: 容错机制、日志、配置管理

### 数据流

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

---

## 配置

### 环境变量

当前项目支持通过环境变量自动映射覆盖 `agent_config.yaml` 中的对应配置项。最常用的环境变量有：

| 环境变量 | 说明 | 映射配置 |
|---------|------|---------|
| `DASHSCOPE_API_KEY` | 用于主对话模型和 embedding | `llm.api_key` |
| `LLM_MODEL` | 指定使用的模型 | `llm.model` |
| `DEBUG` | 开启调试模式 | `app.debug_mode` |
| `LOG_LEVEL` | 指定日志级别 | `app.log_level` |
| `BAIDU_MAPS_MCP_AK` | 供 MCP Server URL 展开使用 | - |

快速开始章节已给出 Windows PowerShell 写入示例；如果你使用其他 shell，只需要设置同名环境变量即可。项目在启动时会自动将环境变量的值注入到全局配置实例中。

### Anthropic 风格 Skill

项目现在支持 Claude/Anthropic 常见的 skill 目录格式，但目录前缀使用项目自己的 `.my_agent`：

```text
.my_agent/
└── skills/
    └── explain-code/
        ├── SKILL.md
        └── reference.md
```

`SKILL.md` 采用 YAML frontmatter + Markdown 正文：

```markdown
---
name: explain-code
description: 解释代码、架构和执行流程；当用户要求「讲解这段代码」「分析模块职责」「说明调用链」时使用。
argument-hint: [文件或主题]
allowed-tools:
  - read
  - grep
  - glob
tags:
  - explanation
  - architecture
---

# Explain Code

优先解释作用、主流程、关键实现和使用方式。
```

使用方式：
- **自动触发**：直接提问「解释 main.py 的主流程」
- **显式触发**：输入 `/explain-code main.py`
- **查看已加载 skills**：在 CLI 中输入 `skills`

完整交互示例见「快速开始 > CLI 快速体验」。skill 既可以作为自动召回能力使用，也可以像命令一样显式触发。

### 配置文件 (agent_config.yaml)

项目使用全局统一的 `agent_config.yaml` 管理系统行为（包括大模型、记忆容量、Token预算、意图识别和安全策略）。如果没有该文件，可以在 CLI 输入 `config` -> `3` 自动生成一份默认配置。

示例 `agent_config.yaml`:

```yaml
llm:
  api_key: null
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
  embedding_url: https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
  temperature: 0.7
  max_tokens: null
  max_retries: 3
  retry_delay: 1.0
  timeout: 60

context:
  system_ratio: 0.2
  history_ratio: 0.6
  file_tree_ratio: 0.05
  terminal_ratio: 0.05
  dynamic_ratio: 0.1

security:
  trusted_domains: null
  acl_config: null

app:
  todo_storage_path: .todos.json
  debug_mode: false
  log_level: INFO
  checkpoint_dir: checkpoints
  vector_db_dir: vectordb
  mcp_data_dir: mcp/mcp_data
  max_recursion_depth: 10
  max_turns_per_agent: 20
  max_buffer_lines: 50
  max_total_tokens_per_agent: 8000
  file_tree_max_depth: 3
  file_tree_max_lines: 50
  file_ref_truncate_length: 500
  recent_file_ops_limit: 5
  terminal_output_lines: 20

mcpServers:
  example-server:
    url: http://localhost:8000/mcp

intent:
  enabled: true
  model: null
  prompt: null
```

需要环境变量展开时，也可以这样写：

```yaml
mcpServers:
  baidu-maps:
    url: https://mcp.map.baidu.com/mcp?ak=${BAIDU_MAPS_MCP_AK}
```

启动 `main.py` 时会自动连接这些 MCP Server，并把远程工具注册到统一工具入口。

### 知识库目录约定

- 默认知识目录是 `knowledge/library`
- 推荐使用 Markdown 标题组织知识，例如 `# / ## / ###`
- 同步后会自动：
  - 解析标题层级
  - 建立 section/chunk 父子关系
  - 在对话时先做层级 RAG 检索，再把结果注入 Prompt
  - 在最终回答末尾追加来源引用

---

## 交互命令

在交互模式下，支持以下快捷命令：

| 命令 | 说明 |
|-----|------|
| `q` / `quit` / `exit` | 退出程序 |
| `plan` | 显示当前任务规划 |
| `tasks` | 显示所有活跃任务 |
| `clear` | 清空 To-do 列表 |
| `undo` | 撤销最后一次更改 |
| `skills` | 显示所有可用 Skills |
| `tools` | 显示所有可用工具 |
| `hooks` | 显示已注册的 Hooks |
| `connect` | 连接 MCP Server |
| `swarm` | 执行蜂群任务 |
| `kn` / `knowledge` | 知识管理菜单 |
| `config` | 配置管理菜单 |
| `cp` / `checkpoint` | 快照管理菜单 |
| `br` / `branch` | 分支管理菜单 |
| `mem` / `memory` / `history` | 查看记忆状态 |

---

## API 参考

详见各模块的文档字符串和类型定义。主要模块：

- `engine.agent`: Agent 主循环和 ReAct 逻辑
- `engine.tools`: 工具执行接口
- `llm.llm`: LLM 调用封装
- `memory.unified_manager`: 统一记忆管理
- `skill.manager`: 技能管理和渐进式披露
- `knowledge.manager`: 知识索引和检索
- `mcp.registry`: MCP 工具注册
- `swarm.planner`: 蜂群任务规划
- `state.session`: 会话状态管理

---

## 设计哲学

> "Simple, Modular, Production-Ready." - 简单、模块化、生产就绪

本项目致力于提供一个**不依赖重型框架**、**完全可控**、**易于理解和扩展**的 AI Agent 基础框架。每个模块都可以独立使用，也可以组合成复杂的 Agent 系统。
