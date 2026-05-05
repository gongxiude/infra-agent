# infra-agent

`infra-agent` 是一个面向基础设施场景的最小化 Python 项目，当前聚焦 Jenkins pipeline、shared library 和 GitOps 仓库任务。

当前实现按 [docs](./docs/README.md) 的前 3 章保留最小闭环：

- Ingestion Plane
- Policy Plane
- Execution Plane
- Integration Plane
- Observability Plane

## 当前能力

- CLI 目录结构对齐 `sre-agent/cli`
- 支持 `local` 和 `remote` 两种客户端模式
- 支持自然语言输入并自动分配任务类型
- 支持 `User Chat`、`Webhooks`、`API Calls`、`Alerts`
- 支持最小 Git workspace 准备流程
- 支持 API、worker、CLI 三条启动链路

## 自然语言分配

默认系统提示词内置了分配策略，当前会把自然语言输入路由到这些任务：

- `jenkins_pipeline_analysis`
- `jenkins_pipeline_change`
- `shared_library_analysis`
- `shared_library_change`
- `gitops_repository_change`
- `alert_triage`
- `chat`

入口来源由真实入口决定：

- CLI 输入和 `/chat` -> `user`
- `/webhooks/jenkins` -> `webhook`
- `/api/tasks` -> `api`
- `/alerts` -> `alert`

## 配置

关键环境变量：

- `AGENT_GIT_REMOTE_REPOSITORIES`
- `AGENT_GIT_WORKSPACE_ROOT`
- `AGENT_GIT_WORKSPACE_DIRECTORIES`

示例：

```bash
export AGENT_GIT_REMOTE_REPOSITORIES='{"jenkins-pipeline":"git@codeup.aliyun.com:6316fd51cb9d00684879aa3a/devops/jenkins-pipeline.git"}'
export AGENT_GIT_WORKSPACE_ROOT=".workspaces"
export AGENT_GIT_WORKSPACE_DIRECTORIES='[".workspaces"]'
```

## 安装

```bash
uv sync --dev
```

## 启动

启动 API：

```bash
uv run infra-agent-runtime
```

启动 worker：

```bash
uv run infra-agent-runtime worker
```

启动 CLI：

```bash
uv run infra-agent
```

## API

- `GET /healthz`
- `POST /chat`
- `POST /webhooks/jenkins`
- `POST /alerts`
- `POST /api/tasks`
- `GET /api/tasks`
- `GET /api/tasks/{task_id}`
- `GET /api/tasks/{task_id}/events`

## 目录

当前保留的源码目录：

- `src/infra_agent/cli`
- `src/infra_agent/config`
- `src/infra_agent/core`
- `src/infra_agent/execution`
- `src/infra_agent/ingestion`
- `src/infra_agent/integrations/git`
- `src/infra_agent/observability`
- `src/infra_agent/policy`

当前实现明确做了减法：

- 删除了之前过多的抽象层
- 删除了失效的复杂数据平面实现
- 删除了不可编译的旧测试与旧运行时胶水代码
- 保留可运行、可测试、可继续迭代的最小版本
