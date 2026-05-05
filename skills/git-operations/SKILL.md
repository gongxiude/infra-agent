# Git Operations

## When To Use
- 当任务涉及 Git workspace 检查、文件分析、diff、commit 或 push 时使用。
- 当任务属于 Jenkins pipeline、shared library、GitOps 或仓库级修改时使用。

## Constraints
- 必须先检查本地 workspace 是否存在，再决定 clone 或复用。
- 不要在没有读取仓库上下文时直接假设文件结构。
- 默认遵循 PR-first 变更控制。

## Error Handling
- 如果 workspace 缺失且 clone 失败，返回明确错误并停止后续仓库修改。
- 如果 Git 命令失败，返回 stderr，并要求先分析失败原因。

## References
- docs/03-tools-skills.md
- docs/07-change-control.md
