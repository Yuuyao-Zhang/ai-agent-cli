# AI Assistant - 生产级 Agentic AI 框架

> 模块化、零依赖、生产级的 AI Agent 框架，支持分层记忆、蜂群智能、状态管理、渐进式技能系统、MCP 协议等高级特性。

本项目是一个**生产级的 Agentic AI 框架**，采用模块化架构设计，使用 Python 标准库实现了完整的 Agent 能力，无需依赖 LangChain 等重型框架。核心特性包括**分层记忆系统**、**蜂群智能协作**、**状态快照与分支管理**、**渐进式披露技能系统**、**MCP 协议集成**、**知识管理**等。

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
- **高级 RAG 检索**: 查询重写 + 多路召回 + 重排序

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
- **文件索引**: 支持单文件和目录批量索引
- **向量搜索**: 基于语义相似度的知识检索
- **标签系统**: 多标签分类管理
- **Prompt 集成**: 检索结果可直接用于上下文

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

### 1. 启动 Agent

```bash
python main.py
```

### 2. 使用分层记忆系统

```python
from state.session import Session
from memory import MemoryManager

session = Session()
memory = MemoryManager(session)

# 添加消息，自动触发记忆管理
memory.add_message("user", "请帮我写一个 Python 函数")
memory.add_message("assistant", "好的，我来帮你...")

# 获取上下文（包含摘要 + 短期记忆）
context = memory.get_context()
```

### 3. 使用状态快照

```python
from state.session import Session
from state.checkpoint import checkpoint_manager

session = Session()

# 创建快照
checkpoint_id = checkpoint_manager.create_checkpoint(session, "手动保存")

# 恢复状态
new_session = checkpoint_manager.load_checkpoint(checkpoint_id)
```

### 4. 使用分支管理

```python
from state.session import Session
from state.branch import branch_manager

session = Session()

# 创建分支
branch_manager.create_branch("feature-branch", session)

# 切换分支
new_session = branch_manager.switch_branch("feature-branch")
```

### 5. 使用蜂群模式

```python
from swarm.planner import MapReducePlanner
from swarm.scheduler import SwarmScheduler

# 分解任务
subtasks = MapReducePlanner.decompose("分析项目代码结构")

# 并行执行
scheduler = SwarmScheduler(max_workers=5)
results = scheduler.run_batch(subtasks, session)
```

### 6. 使用渐进式披露技能

```python
from skill import SkillManager, DisclosureLevel

manager = SkillManager("skills")
manager.initialize()

# 按级别获取技能信息
brief = manager.get_skill_disclosed("pdf", DisclosureLevel.BRIEF)
detailed = manager.get_skill_disclosed("pdf", DisclosureLevel.DETAILED)
```

### 7. 使用安全系统

```python
from common.security import SecurityManager

security = SecurityManager(current_role="user")

# 检查权限
if security.can_use_tool("bash"):
    # 执行操作
    pass

# 授权检查
allowed, reason = security.check_authorization("write", "/etc/passwd")
```

### 8. 使用知识管理

```python
from knowledge import knowledge_manager

# 索引文件
knowledge_manager.index_file("document.pdf")

# 搜索知识
results = knowledge_manager.search("Python 装饰器", top_k=5)
```

### 9. 使用 MCP 工具

```python
from mcp.registry import registry

# 连接 MCP Server
registry.connect_mcp_server("http://localhost:8000/mcp")

# 查看可用工具
tools = registry.list_all_tools()
```

支持多个 MCP Server，按 `mcpServers.<name>.url` 配置；客户端会先执行标准 MCP 初始化，再自动发现工具。

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
MemoryManager (分层记忆检索)
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
# LLM 配置
export DASHSCOPE_API_KEY="your-api-key"
export LLM_MODEL="qwen-plus"

# 可选配置
export MAX_RECURSION_DEPTH=10
export MAX_TOTAL_TOKENS=8000
export DEBUG=true
```

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

---

## API 参考

详见各模块的文档字符串和类型定义。

---

## 设计哲学

> "Simple, Modular, Production-Ready." - 简单、模块化、生产就绪

本项目致力于提供一个**不依赖重型框架**、**完全可控**、**易于理解和扩展**的 AI Agent 基础框架。每个模块都可以独立使用，也可以组合成复杂的 Agent 系统。
