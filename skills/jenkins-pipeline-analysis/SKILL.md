---
name: jenkins-pipeline-analysis
description: Jenkins pipeline、job DSL 和流水线结构分析指南
---

# Jenkins Pipeline Analysis

## When To Use
- 当任务涉及 Jenkins pipeline、pipeline job 或流水线维护时使用。
- 当需要分析 Jenkinsfile、job DSL 或相关仓库结构时使用。

## Constraints
- 必须在目标仓库 workspace 中执行分析。
- 不要脱离真实仓库结构输出泛化修改建议。

## Error Handling
- 如果找不到目标文件，先返回仓库结构检查结果。
- 如果需要更多上下文，先读取相邻文件再继续分析。

## References
- docs/01-architecture.md
- docs/03-tools-skills.md
