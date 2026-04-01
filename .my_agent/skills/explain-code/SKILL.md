---
name: explain-code
description: 解释代码、架构和执行流程；当用户要求“讲解这段代码”“分析模块职责”“说明调用链”时使用。
argument-hint: [文件或主题]
allowed-tools:
  - read
  - grep
  - glob
tags:
  - explanation
  - architecture
  - walkthrough
---

# Explain Code

当你被自动召回或用户显式以 `/explain-code` 调用时，优先执行以下流程：

1. 先识别用户要理解的是文件、函数、模块、调用链还是整体架构。
2. 优先给出“它是做什么的”，再解释“它如何工作”，最后解释“为什么这样设计”。
3. 如果涉及代码链路，给出关键入口、核心函数、重要数据流和边界条件。
4. 解释时尽量使用分层结构，不要只复述代码。
5. 如果用户传入参数 `$ARGUMENTS`，把它视为要重点解释的对象。

对代码讲解时，额外遵循 [reference.md](reference.md) 中的输出结构。
