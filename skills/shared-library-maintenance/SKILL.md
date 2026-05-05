---
name: shared-library-maintenance
description: Jenkins shared library 目录结构、vars/src 分析和维护指南
---

# Shared Library Maintenance

## When To Use
- 当任务涉及 Jenkins shared library 的分析或修改时使用。
- 当需要在仓库中定位共享库目录、vars、src 或 resources 结构时使用。

## Constraints
- 必须先读取已有 shared library 结构和约定。
- 不要在没有 diff 和验证上下文的情况下直接提交大范围修改。

## Error Handling
- 如果无法确认 shared library 入口，先列出目录结构并停止。
- 如果存在多套约定，先返回冲突点。

## References
- docs/03-tools-skills.md
- docs/07-change-control.md
