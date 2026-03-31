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

### 2. 分层记忆系统 (Hierarchical Memory)
- **三层记忆架构**: 短期记忆(活跃窗口) → 中期记忆(SQLite摘要) → 长期记忆(向量索引)
- **滑动窗口摘要**: 自动压缩历史对话，保留关键信息
- **Token 预测器**: 基于历史消耗预测未来 Token 需求
- **上下文剪枝**: 结合摘要与活跃窗口控制 Prompt 大小

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

### 5. 渐进式披露技能系统 (Progressive Disclosure)
- **四级披露机制**: BRIEF → SUMMARY → DETAILED → FULL
- **上下文感知**: 根据用户查询智能调整信息披露级别
- **依赖管理**: DAG 拓扑排序，自动解析技能依赖
- **热重载**: 文件变更自动重载，无需重启
- **语义检索**: 向量索引支持技能语义搜索

### 6. 安全系统 (Security)
- **2D ACL 矩阵**: 角色 × 工具 的细粒度权限控制
- **三级角色**: admin / user / guest
- **风险评分**: 0-10 级评分 + 歧义加权因子
- **HITL 确认**: 高风险操作人工确认机制
- **敏感操作检测**: 危险命令正则匹配
- **敏感路径保护**: 系统关键目录访问控制

### 7. 知识管理 (Knowledge Management)
- **自动同步**: `knowledge/library` 下的 `.md` / `.txt` 文件可一键同步
- **层级 RAG**: 按 Markdown 标题解析 section/chunk 父子结构
- **父子检索**: 先召回标题章节，再过滤并重排子块
- **结果去噪**: 标题重叠加权、代码块降权、目录节点过滤、同 section 去重
- **回答引用**: 最终回答会自动附带知识来源引用

### 8. MCP 协议集成
- **动态工具发现**: 自动发现 MCP Server 提供的工具
- **多 Server 支持**: 可同时连接多个 MCP Server
- **路由策略**: FIRST_AVAILABLE / ROUND_ROBIN / RANDOM
- **统一接口**: 本地工具与远程 MCP 工具统一调用

### 9. 任务规划 (Todo System)
- **状态管理**: PENDING/IN_PROGRESS/COMPLETED/FAILED/SKIPPED
- **版本历史**: 支持撤销/重做，最多保留10个快照
- **可视化渲染**: 美观的终端输出格式

---

## 项目结构

```text
.
├── engine/             # 核心引擎
│   ├── agent.py        # Agent 主循环，集成所有组件
│   ├── tools.py        # 工具执行 (bash/read/write/edit/todo/subtask)
│   └── hooks.py        # AOP Hook 系统
├── llm/                # LLM 接口
│   ├── llm.py          # 通义千问调用，零依赖实现
│   ├── context.py      # 上下文组装器，Token 预算管理
│   ├── parser.py       # 指令解析
│   └── terminal.py     # 终端输出捕获
├── memory/             # 分层记忆系统
│   ├── manager.py      # 分层记忆管理器
│   ├── unified_manager.py  # 统一记忆管理器
│   ├── stores/         # 三层存储 (短期/中期/长期)
│   ├── retriever/      # RAG 检索 (重写/召回/重排)
│   └── vector/         # 向量处理
├── state/              # 状态管理
│   ├── session.py      # 会话状态，支持 fork 和快照
│   ├── manager.py      # 任务生命周期管理
│   ├── task.py         # 任务状态定义
│   ├── namespace.py    # 变量命名空间
│   ├── checkpoint.py   # 状态快照
│   └── branch.py       # 分支管理
├── swarm/              # 蜂群智能
│   ├── planner.py      # MapReduce 任务分解
│   ├── scheduler.py    # DAG 任务调度
│   ├── factory.py      # Agent 工厂
│   └── consensus.py    # 结果共识
├── skill/              # 技能系统
│   ├── types.py        # 技能类型定义
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
│   ├── store.py        # Todo 存储与版本控制
│   └── render.py       # 可视化渲染
├── common/             # 通用组件
│   ├── config.py       # 配置管理
│   ├── security.py     # 安全策略与 ACL
│   ├── logger.py       # 日志系统
│   ├── constant.py     # 常量定义
│   ├── io_utils.py     # IO 工具
│   ├── file_lock.py    # 文件锁
│   └── vector/         # 向量工具
│       ├── tokenizer.py   # 分词器
│       └── similarity.py  # 相似度计算
└── main.py             # 主入口
```

---

## 快速开始

### 1. 配置系统环境变量

在首次启动前，建议先把必要配置写入**系统环境变量**。

Windows PowerShell 示例：

```powershell
[System.Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "你的通义千问 API Key", "User")
[System.Environment]::SetEnvironmentVariable("LLM_MODEL", "qwen-plus", "User")
[System.Environment]::SetEnvironmentVariable("BAIDU_MAPS_MCP_AK", "你的百度地图 AK", "User")
```

说明：
- `DASHSCOPE_API_KEY`：必需，用于主对话模型和 embedding
- `LLM_MODEL`：可选，默认是 `qwen-plus`
- `BAIDU_MAPS_MCP_AK`：仅在你配置百度地图 MCP 时需要

设置完成后，请**关闭并重新打开终端**，让新环境变量生效。

### 2. 启动 Agent

```bash
python main.py
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

### 4. 真实对话示例

下面是一个启动 `main.py` 后的真实使用方式，包含知识同步、菜单搜索和正常提问：

```text
$ python main.py

用户 (kn知识, config配置, cp快照, br分支, mem记忆, swarm蜂群, q退出)> kn

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

用户 (kn知识, config配置, cp快照, br分支, mem记忆, swarm蜂群, q退出)> Python 默认参数 exponent=2 是什么意思

FINAL RESULT:
在 Python 中，`exponent=2` 是函数定义中的默认参数，表示调用函数时如果没有显式传入 `exponent`，就自动使用值 `2`。

例如：
def power(base, exponent=2):
    return base ** exponent

- power(5) 等价于 power(5, 2)
- power(5, 3) 会覆盖默认值

知识来源引用:
- python_base.md | python_base > Python 基础 > Python 函数基础 | Chunk 2/3
```

### 5. 再试一个层级 RAG 问题

```text
用户 (kn知识, config配置, cp快照, br分支, mem记忆, swarm蜂群, q退出)> Python 描述符协议是做什么的
```

这类问题会优先命中 `python_advanced.md` 中对应的标题章节，再从该章节下召回最相关的子块进行回答。

### 6. MCP 配置示例

项目支持通过 `mcpServers.<name>.url` 自动连接多个 MCP Server：

```yaml
mcpServers:
  baidu-maps:
    url: https://mcp.map.baidu.com/mcp?ak=${BAIDU_MAPS_MCP_AK}
```

启动 `main.py` 时会自动完成标准 MCP 初始化并注册远程工具。

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
ContextAssembler (Token 预算分配)
    ↓
MemoryManager (分层记忆视图)
    ↓
KnowledgeManager (层级 RAG 检索 + 来源引用)
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

```bash
# 必需：主对话与 embedding
export DASHSCOPE_API_KEY="your-api-key"

# 可选：覆盖默认模型
export LLM_MODEL="qwen-plus"

# 可选：接入百度地图 MCP 时使用
export BAIDU_MAPS_MCP_AK="your-baidu-ak"

# 可选：调试模式
export DEBUG=true
```

Windows PowerShell 永久写入示例：

```powershell
[System.Environment]::SetEnvironmentVariable("DASHSCOPE_API_KEY", "your-api-key", "User")
[System.Environment]::SetEnvironmentVariable("LLM_MODEL", "qwen-plus", "User")
[System.Environment]::SetEnvironmentVariable("BAIDU_MAPS_MCP_AK", "your-baidu-ak", "User")
```

当前项目代码中，以下环境变量会被直接读取：
- `DASHSCOPE_API_KEY`：优先级高于配置文件
- `LLM_MODEL`：优先级高于配置文件
- `DEBUG`：开启调试模式
- `BAIDU_MAPS_MCP_AK`：供 `agent_config.yaml` 中的 `${BAIDU_MAPS_MCP_AK}` 展开使用

### 配置文件

创建 `agent_config.yaml`:

```yaml
llm:
  api_key: null
  model: qwen-plus
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions
  embedding_url: https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
  temperature: 0.7
  max_tokens: null

security:
  trusted_domains: null
  acl_config: null

app:
  todo_storage_path: .todos.json
  debug_mode: false
  log_level: INFO
  checkpoint_dir: checkpoints
  vector_db_dir: vectordb

mcpServers:
  example-server:
    url: http://localhost:8000/mcp
```

例如接入需要 AK 的服务时，也可以这样写：

```yaml
mcpServers:
  baidu-maps:
    url: https://mcp.map.baidu.com/mcp?ak=${BAIDU_MAPS_MCP_AK}
```

### 知识库目录约定

- 默认知识目录是 `knowledge/library`
- 推荐使用 Markdown 标题组织知识，例如 `# / ## / ###`
- 同步后会自动：
  - 解析标题层级
  - 建立 section/chunk 父子关系
  - 在对话时先做层级 RAG 检索，再把结果注入 Prompt
  - 在最终回答末尾追加来源引用

---

## API 参考

详见各模块的文档字符串和类型定义。

---

## 设计哲学

> "Simple, Modular, Production-Ready." - 简单、模块化、生产就绪

本项目致力于提供一个**不依赖重型框架**、**完全可控**、**易于理解和扩展**的 AI Agent 基础框架。每个模块都可以独立使用，也可以组合成复杂的 Agent 系统。
