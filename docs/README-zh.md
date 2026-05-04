# Infrastructure Agents 指南

[![License: CC BY 4.0](https://img.shields.io/badge/License-CC_BY_4.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)
[![Code License: MIT](https://img.shields.io/badge/Code_License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Chapters: 13](https://img.shields.io/badge/Chapters-13-green.svg)](#指南结构)

> 如何为基础设施团队安全地设计、构建和运营 AI agents。

AI agents 可以编写 IaC、修复 compliance finding、检测 drift、review PR，并自主响应 incident。但没有 guardrails 的 autonomy 是一种负担。能够执行 `terraform apply` 的 agents 同样也能执行 `terraform destroy`。能读取 config 的 agents 也可能泄露 secrets。会循环执行的 agents 还可能烧掉预算。

**本指南覆盖了你在构建基础设施 agents 时需要做出的每一个架构决策**，包括真实模式、代码片段、多种备选方案，以及用于评估这些选择的风险框架。

---

## 适用对象

- **Platform engineers**，正在评估应自行构建还是采购 agent 能力
- **SREs**，正在为 incident response 和 remediation 设计安全自动化
- **DevOps leads**，正在构建 self-service IaC 平台
- **Engineering leaders**，需要一套经过审查的 AI 驱动基础设施架构

---

## 指南结构

| # | 章节 | 你将学到什么 |
|---|---------|-------------------|
| 1 | [架构概览](./01-architecture-zh.md) | infra-agent system 的六个 plane |
| 2 | [Agent Runtime 与 Orchestration](./02-agent-runtime-zh.md) | LLM runtimes（Claude Agent SDK、OpenAI、LangChain、自定义方案）、task queuing、worker isolation |
| 3 | [Tools、CLIs 与 Skills](./03-tools-skills-zh.md) | CLI tooling、skills、managed subagents、MCP，以及 capability management |
| 4 | [Sandboxed Execution](./04-sandboxed-execution-zh.md) | 使用 Docker、Modal、Azure Container Apps 的 container isolation |
| 5 | [Credential Management](./05-credential-management-zh.md) | short-lived tokens、vault patterns、blast radius control |
| 6 | [Data Plane](./06-data-plane-zh.md) | 基础设施 knowledge layer、resource graphs、context serialization |
| 7 | [Change Control 与 GitOps](./07-change-control-zh.md) | 基于 PR 的 workflows、drift verification、validation loops |
| 8 | [Policy 与 Guardrails](./08-policy-guardrails-zh.md) | tool restrictions、approval gates、autonomy tiers |
| 9 | [Observability 与 Audit](./09-observability-zh.md) | OpenTelemetry、action trails、debugging agent failures |
| 10 | [Autonomous Operations 与 Notifications](./10-autonomy-notifications-zh.md) | scheduling、autonomous agents、notification routing、escalation chains |
| 11 | [Testing 与 Hardening](./11-testing-hardening-zh.md) | trajectory tests、prompt injection defense、security benchmarks |
| 12 | [UX 与 Usability](./12-ux-usability-zh.md) | multi-tenancy、RBAC、onboarding、team collaboration、error prevention |
| 13 | [Risk Framework 与 Checklists](./13-risk-framework-zh.md) | decision matrices、compliance mapping、go-live checklists |

---

## 核心原则

1. **Agents 默认采用 PR-First Change Control**。每一次基础设施变更都通过 pull request 流转。agent 产出的是 diff，而不是 deployment。如果你确实支持 direct execution，应将其视为独立的 break-glass architecture，并配套独立的 credentials、approval paths 和 audit controls。
2. **默认采用 Least Privilege**。Agents 只获取完成任务所需的最小 credentials 和 tool access。权限应被限定范围、设置时效，并且可审计。
3. **Observability 不是可选项**。每一次 tool call、credential request 和 decision point 都必须具备端到端的 logging 和 tracing。
4. **要 Fail Safe，而不是 Fail Open**。一旦存在疑问，agent 就应停止并请求人工介入。timeouts 和 policy gates 是架构性约束，不是建议。
5. **Agent 没有特殊待遇**。由 agent 发起的变更应与人工发起的变更走相同的 review、CI 和 deployment pipeline。

---

## 快速开始：Mental Model

```
┌───────────────────────────────────────────────────────────┐
│                    你的基础设施                           │
│  AWS / Azure / GCP / OCI    Terraform / Bicep / Pulumi    │
│  GitHub / GitLab / ADO      Prowler / Checkov / Custom    │
└────────────────────────────┬──────────────────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │    POLICY PLANE     │  ← agents 能做什么
                  │  (rules, approvals) │
                  └──────────┬──────────┘
                             │
            ┌────────────────▼────────────────┐
            │          AGENT RUNTIME          │
            │  Skills · Subagents · Tools     │  ← agents 如何执行
            │  Credentials · Sandboxing       │
            └────────────────┬────────────────┘
                             │
                  ┌──────────▼──────────┐
                  │   CHANGE CONTROL    │  ← 变更如何落地
                  │  (PRs, validation)  │
                  └──────────┬──────────┘
                             │
                  ┌──────────▼──────────┐
                  │    OBSERVABILITY    │  ← 你如何看到全过程
                  │  (traces, alerts)   │
                  └─────────────────────┘
```

---

## 覆盖的备选方案

本指南并不规定单一技术栈。对于每一层架构，我们都会覆盖多种实现路径：

| Layer | 覆盖的选项 |
|-------|----------------|
| **LLM Runtime** | Claude Agent SDK、OpenAI Agents SDK / Codex CLI、LangChain/LangGraph、direct API |
| **Agent Roles** | managed/project subagents、app-level agent configs、plugins |
| **Task Queue** | Redis Streams、BullMQ、AWS SQS、RabbitMQ、Temporal |
| **Sandboxing** | Docker、Modal、Azure Container Apps Jobs、AWS Lambda、Firecracker |
| **Credential Store** | HashiCorp Vault、AWS Secrets Manager、Azure Key Vault、1Password |
| **Change Control** | GitHub Actions、GitLab CI、Azure Pipelines、Atlantis、Spacelift |
| **Observability** | OpenTelemetry + Grafana、Datadog、Dash0、New Relic |
| **Interoperability** | MCP、A2A |
| **Notifications** | Slack、Microsoft Teams、PagerDuty、Opsgenie、email、webhooks |
| **Scheduling** | Cron（systemd/k8s）、Temporal、AWS EventBridge、Azure Timer Triggers |
| **State Storage** | PostgreSQL、Redis、Azure Blob、S3、SQLite |

---

## 贡献

发现错误？有更好的模式？欢迎贡献。

- **Issues**：用 issue 提交问题、建议或修正
- **Pull Requests**：提交 PR 以改进内容或补充新的示例
- **Discussions**：使用 GitHub Discussions 讨论更广泛的架构问题

请将贡献重点放在模式与架构上，而不是特定厂商的营销内容。

---

## 关于本项目

本指南由 **[Cloudgeni](https://cloudgeni.ai)** 团队构建。我们为企业团队在 AWS、Azure、GCP 和 OCI 上设计、构建并运营生产级 autonomous infrastructure agents。

这里的每一种模式都来自这些系统在生产环境中的实际运行经验。我们之所以将其开源，是因为我们不断重复回答同样的架构问题。把它们一次性写下来显然更有价值。

---

## 许可

指南正文基于 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 发布。你可以使用、改编和分享，只需注明来源。

代码片段基于 [MIT](https://opensource.org/licenses/MIT) 发布。
