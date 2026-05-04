# 第 12 章：UX、Usability 与 Team Onboarding

> 如何打包基础设施 agents，让每个人都能安全采用，而不需要先读完整套 11 章指南。

---

## Usability Problem

你已经构建了 agent runtime、sandbox、credential broker、policy engine 和 observability stack。现在你有了一个只有你自己能理解的系统。

难点不在于让 agents 跑起来，而在于让一个**3 人的平台团队为 5 个团队的 50 名工程师服务**时，这套系统仍然可用，不会成为 bottleneck，也不会让一名初级开发者不小心给 agent 配上 production admin credentials。

---

## 设计原则：让安全路径成为最容易的路径

每一个 UX 决策都应遵循一条规则：

> **默认行为应当是安全行为。做错事所需的成本，应高于做对事。**

示例：
- 新 agent 默认是 plan-only mode，想获得 apply access 需要显式 escalation
- Credentials 默认只作用于单个 cloud account，cross-account access 需要 admin 操作
- Agent sessions 默认 private，sharing 需要显式开关
- PR review 采用 per-repository opt-in，而不是一个全局开关

如果你发现自己在构建“are you sure?”确认弹窗，说明 UX 已经失败了。系统应被设计为：危险动作在没有刻意的、admin-level 配置之前根本不可达。

---

## Multi-Tenancy：以 Organization 作为安全边界

Organization 是**最高级别的 isolation boundary**。所有东西，包括 credentials、repositories、agents、policies、sessions、variables，都必须以 organization 为作用域：

- Company A 的 platform engineer **不能**看到 Company B 的基础设施
- 同一 organization 内的 team **可以**彼此共享 agent sessions
- Org X 的 admin **不能**升级到 Org Y，即使这两者是同一个人

```
┌────────────────────────────────────────────────────────────┐
│  Organization: "Acme Platform Team"                        │
│                                                            │
│  Cloud accounts: AWS Prod, AWS Staging, Azure Dev          │
│  Repositories:   infra-core, app-deploy, data-pipelines    │
│  Agents:         remediation, drift, PR review, devops     │
│  Policies:       "encrypt all S3", "tag everything"        │
│  Members:        alice (admin), bob (member), carol        │
└────────────────────────────────────────────────────────────┘

  ← No data crosses this boundary →

┌────────────────────────────────────────────────────────────┐
│  Organization: "Acme App Team"                             │
│  (Separate credentials, repos, agents, policies)           │
└────────────────────────────────────────────────────────────┘
```

关键实现规则是：**每一个 database query 都必须包含 organization filter**。通过 middleware 强制执行，在任何 handler 运行前先验证 org membership。跨 org 访问应返回 403，而不是 404，不要泄露对象存在性。

Organizations 可以映射到用户现有的 VCS 结构（GitHub organizations、GitLab groups），这样 repositories 和 team membership 就能自动导入。

---

## RBAC：角色保持简单，安全依赖结构

### 保持角色简单

复杂的角色层级只会制造困惑。三个角色可以覆盖 95% 的需求：

| Role | Can Do | Cannot Do |
|------|--------|-----------|
| **Admin** | 管理 members、integrations、credentials、policies、agent configs | 访问其他 organizations |
| **Member** | 使用 agents、查看 sessions、创建 PRs、运行 scans、查看 findings | 修改 integrations、管理 members、变更 policies |
| **Viewer** | 查看 dashboards、sessions、findings（只读） | 触发 agents、修改任何内容 |

### 安全应该存在于结构中，而不是依赖角色

核心洞察是：**不要依赖角色来防止错误。要把系统设计成错误根本不可能发生。**

| Risk | Bad Approach (role-based) | Good Approach (structural) |
|------|--------------------------|---------------------------|
| 初级开发者给 agent 配置 prod creds | “只有 admins 才能选择 integrations” | Agent 只能访问 admin 预先配置好的 integrations。agent UI 中根本没有“输入 credentials”字段。 |
| Developer 启用 apply mode | “只有 admins 可以变更 agent tier” | Apply mode 需要一套 members 无法创建的独立 credentials。agent config 仅 admin 可改。 |
| 新成员访问了错误 repo | “依赖 repository access 的 RBAC” | Repositories 按 org 隔离。成员只能看到连接到自己 org 的 repos。 |
| 某人共享了包含 secrets 的 session | “警告用户不要共享” | 自动进行 log redaction。含 credential requests 的 sessions 默认输出已脱敏。 |

---

## Onboarding：在几分钟内获得价值

### 从两步开始，而不是十五步

不要一开始就展示 wizard。起步只做两件事：

```
GET STARTED
You need two things to start using infrastructure agents:

  1. CONNECT CLOUD            2. CONNECT GIT REPO
     AWS / Azure /               GitHub / GitLab /
     GCP / OCI                   Azure DevOps
     [Quick Connect]             [Connect Provider]

After these, agents can analyze your infrastructure
and start creating PRs.
```

其他一切都应是渐进式展示，只有在必需步骤完成后才显示。

### Quick Connect：不要复制粘贴 Credentials

这是最快获得价值的路径。用户永远不应手动输入 access keys。

- **AWS**：一键部署 CloudFormation stack，创建一个信任你平台的 cross-account IAM role。约 30 秒。
- **Azure**：OAuth consent flow 自动创建 service principal。约 10 秒。
- **GCP**：Workload Identity Federation 或 OAuth consent。无需 service account key files。

**关键原则**：Quick Connect 应使用标准 delegation 机制（cross-account roles、OAuth、OIDC），让 long-lived credentials 不经过人手。

### Progressive Disclosure

在完成两个必需步骤之后，根据用户已经解锁的能力再逐步展示功能：

```
Phase 1 (mandatory):  Connect cloud + Connect Git
Phase 2 (suggested):  Run first compliance scan → Run static analysis → Fix first finding
Phase 3 (optional):   Enable drift detection, automated PR review, invite team members
```

在必需步骤完成之前持续显示 onboarding progress，完成后就隐藏。不要对已经过了基础阶段的用户反复 nag。

---

## Self-Service Agent Interface

### 以 Chat 作为主要界面

主要界面应像一场对话，而不是一个 CI/CD dashboard。三个 selector 就足以为 agent 提供上下文：

```
[Agent: DevOps ▼]  [Repo: infra-core ▼]  [Cloud: AWS ▼]

┌─────────────────────────────────────────────────────┐
│  Fix the S3 bucket encryption finding for           │
│  my-data-bucket                                     │
│                                          [Send ->]  │
└─────────────────────────────────────────────────────┘
```

**为什么这样有效**：Members 不需要了解 credentials、pipelines 或 agent configurations。Admin 已经完成 integrations 配置。Member 只需要从下拉框中选择，并提出问题。

### Prompt Discovery：不要让用户猜该问什么

新用户并不知道该怎么问。应提供按类别整理的起始 prompts：

- **Fix Compliance**："Find my top 3 critical issues and fix them"、"Remediate all HIGH severity findings"
- **Create Resources**："Create an S3 bucket with versioning and encryption"、"Set up a VPC with public and private subnets"
- **Refactor**："Convert inline security groups to named resources"、"Split this monolithic config into modules"
- **Analyze**："Explain how my infrastructure is set up"、"Show me all security groups with open SSH access"

### Deep-Link Support

允许从任意位置触发 agents，compliance dashboards、Slack、CI/CD 都可以：

```
/agent-sessions?agent=remediation&repo=xxx&prompt=Fix+finding+ABC123
```

在 compliance finding 卡片上放一个 “Fix with Agent” 按钮，可以预填 agent、repo 和 prompt，实现一键启动 remediation。

---

## Session Sharing 与 Collaboration

### Default-Private，按需 Opt-In Sharing

Agent sessions 常常包含并非所有人都该看到的基础设施细节。默认应为 private，并通过显式开关允许在 organization 内共享。

```
Session List:
┌──────────────────────────────────────────┐
│ ● Fix S3 encryption           Private    │
│ ● Drift remediation           Shared     │
│ ● VPC refactoring (Bob)       From Bob   │
│ ● Compliance scan review      Private    │
└──────────────────────────────────────────┘
```

实时多光标协作没有必要，agent sessions 是顺序型的（一名用户提问，agent 响应）。更有价值的是提供**sharing**（其他人查看发生了什么）、**forking**（从某个特定点继续），以及 **session history**（供团队 review 的 audit trail）。

---

## 用 Plain Language 编写 Policies

基础设施团队已经很难应对 Rego、Sentinel 和 OPA 了。Agent policies 应使用**plain language**，让任何工程师都能读懂和编写：

```markdown
## Policy: Encryption Requirements

- All S3 buckets MUST have server-side encryption enabled (SSE-KMS preferred)
- All RDS instances MUST have storage encryption enabled
- When fixing encryption findings, use the organization's KMS key: alias/infra-key
- Never disable encryption on existing resources, even temporarily
```

Agent 会将这部分内容读入自身 context。Policy 应具备 versioning、auditability，并且对于编写者、reviewer，以及排查“为什么 agent 会这么做”的人来说，都是可理解的。

为常见标准（encryption、tagging、network access）提供 **policy templates**，避免团队从空白开始。跟踪每一次 policy change，并保留 version history 和 diffs。

---

## Variable Scoping：在不增加复杂性的前提下实现环境隔离

Variables（backend addresses、region defaults、environment config）遵循三级 override 链：

```
Repository scope    (highest priority — overrides everything)
  ↓
Integration scope   (overrides org level)
  ↓
Organization scope  (baseline defaults)
```

Platform team 可以在 org 级别设置 `TF_BACKEND_BUCKET=acme-terraform-state`。如果某些 team 使用不同 backend，它们可以在 repo 级别覆盖，而双方都不需要理解彼此的配置。Secret variables 在静态存储时应加密，保存后在 UI 中隐藏。

---

## Per-Repository Agent Configuration

并不是所有功能都应全局开启。关键的 per-repo 控制包括：

- **Automated PR review**：按 repository opt-in。启用后，已配置的 review agent 会在包含 IaC 变更的新 PR 上自动 dispatch。开发者无需任何配置，就能看到 review comments 自动出现。
- **IaC pipelines**：由 admins 配置（使用哪个 CI system、哪个 workflow、每个 environment 的 overrides）。Members 通过 agents 与 pipelines 交互，例如“validate my changes”，而不是自己编辑 pipeline definitions。

---

## 防止初级开发者犯错

### 错误预防层级

从最有效到最不有效：

```
1. MAKE IT IMPOSSIBLE  — Structure prevents the mistake entirely
2. MAKE IT HARD        — Extra steps required, admin approval needed
3. MAKE IT VISIBLE     — Clear warnings, confirmation dialogs
4. MAKE IT REVERSIBLE  — Easy rollback, audit trail
```

| Mistake | Prevention (Level) |
|---------|-------------------|
| 给 agent 配置 prod credentials | Cloud integrations 由 admin 配置。Members 只从下拉框选择，绝不手动输入 creds。**(Impossible)** |
| 直接执行 `terraform apply` | System prompts 含有禁止 apply 的硬规则。Tool allow-list 也排除了 apply。**(Impossible)** |
| 访问其他 team 的资源 | Organization boundary 隔离全部数据。不存在跨 org query path。**(Impossible)** |
| Push 到 main branch | Agent hard rules + branch protection rules。**(Hard)** |
| 共享包含敏感数据的 sessions | Default-private sessions + automatic log redaction。**(Hard)** |
| 忘记在 PR 前做 validation | Agent 的 validation loop 会自动执行。没有 skip 选项。**(Impossible)** |

用于 programmatic access 的 API keys 应在创建时就绑定 organization scope，且不能被重新分配给另一个 org。

---

## Notification Preferences

Notification fatigue 会扼杀采用率。需要两级控制：

- **Organization-level**：Admin 一次性配置 Slack/Teams webhook，并切换哪些 event types 要发到该 channel。整个团队无需个人配置即可受益。
- **Per-user**：每个成员控制自己的 email digest frequency、quiet hours，以及按类别的开关（security findings、remediation status、product updates）。

---

## UX 对比：Team Onboarding 的不同方案

| Approach | Time to First Value | Admin Effort | Junior Safety | Collaboration |
|----------|-------------------|-------------|--------------|---------------|
| **Org-based multi-tenancy** (recommended) | Minutes (quick connect) | Low (one-time setup) | High (structural isolation) | Good (shared sessions, per-repo config) |
| **Per-user permissions** | Hours (configure each user) | High (ongoing) | Medium (role-dependent) | Poor (manual sharing) |
| **Namespace/project-based** | Medium | Medium | Medium | Medium |
| **Single-tenant deployment** | Days (deploy per team) | Very high | High (full isolation) | None (no cross-team visibility) |
| **No isolation** (everyone is admin) | Instant | None | None | Full (no privacy) |

---

## 下一章

[第 13 章：Risk Framework 与 Checklists →](./13-risk-framework-zh.md)

---

*Built by the team at [Cloudgeni](https://cloudgeni.ai) — Scale your infrastructure team. With Agents. Safely.*
