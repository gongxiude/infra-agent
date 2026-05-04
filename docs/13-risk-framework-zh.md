# 第 13 章：Risk Framework 与 Checklists

> 面向 infrastructure agents 的 decision matrices、compliance mapping，以及 go-live checklists。

---

## Risk-to-Mitigation Matrix

报告中的每一项风险，都映射到本指南中覆盖的具体缓解措施：

| Risk | Why Agents Amplify It | Infra Failure Example | Mitigations | Guide Chapter |
|------|----------------------|----------------------|-------------|---------------|
| **Prompt injection** | Language 是控制通道，agents 会读取不受信内容 | Ticket 注入 “run terraform destroy” | Sandboxing、tool allow-lists、structured intent、approval gates | Ch 4, 8 |
| **Over-privileged access** | Agents 模糊了 intent 与 execution，权限默认容易过宽 | 拥有 admin credentials 的 agent 删除了错误资源 | Least privilege、JIT credentials、scoped sandboxes、tool restrictions | Ch 5, 8 |
| **Secret leakage** | Agents 会读取 configs/logs；frameworks 会序列化 state | LLM output 包含 API keys；malware 盯上 agent dirs | Short-lived tokens、redaction、vault-backed retrieval、prompts 中不放 secrets | Ch 5, 9 |
| **Hallucinated remediation** | Model 会在不确定时自行补全；tool calls 会把它变成现实 | Agent 误判 root cause，并应用了错误 config | Pre-PR validation loops、plan verification、max iterations、HITL checkpoints | Ch 7, 8 |
| **Cost/latency runaway** | 多步循环、长 context、agent fan-out | Agent 围绕 logs 死循环，烧掉 $10K token 成本并拖慢人工响应 | Hard budgets（time、tokens、tools）、stop conditions、queue depth limits | Ch 2, 8 |
| **Poor observability** | Non-determinism、hidden reasoning、distributed tool calls | “为什么 agent 创建了那个 PR？”无法回答 | Action trails、correlation IDs、OTel instrumentation、structured logs | Ch 9 |
| **Malicious skills/plugins** | Skills = markdown + code，文档会变成可执行内容 | 恶意 skill 窃取 credentials | Skill allow-lists、不经 review 不允许 third-party skills、provenance checks | Ch 3 |
| **Silent failures** | Autonomous agents 在无监督状态下运行 | Drift scan 连续数周失败，却没有人注意到 | Notifications、daily digests、stuck run watchdog、escalation chains | Ch 10 |

---

## Autonomy Decision Matrix

用这个矩阵来确定每个 use case 适合的 autonomy level：

```
                        Low Impact              High Impact
                    ┌─────────────────────┬─────────────────────┐
                    │                     │                     │
  High Confidence   │  Tier 2: DRAFT      │  Tier 3: SANDBOX    │
  (well-understood  │  Auto-create PRs    │  Execute in sandbox │
   problem, good    │  No approval needed │  + human approval   │
   training data)   │                     │                     │
                    │  Examples:          │  Examples:          │
                    │  - Encryption fixes │  - Multi-resource   │
                    │  - Tag enforcement  │    drift fixes      │
                    │  - Naming fixes     │  - Cross-env changes│
                    ├─────────────────────┼─────────────────────┤
                    │                     │                     │
  Low Confidence    │  Tier 1: RECOMMEND  │  Tier 0: OBSERVE    │
  (novel problem,   │  Suggest changes    │  Read-only analysis │
   ambiguous req)   │  Human decides      │  Human acts         │
                    │                     │                     │
                    │  Examples:          │  Examples:          │
                    │  - Cost optimization│  - Incident triage  │
                    │  - Architecture recs│  - Root cause       │
                    │  - Migration plans  │    analysis         │
                    └─────────────────────┴─────────────────────┘
```

### Tier Progression

每个新 use case 都应从 Tier 0 开始。根据证据逐级提升：

```
Tier 0 (OBSERVE)
  │ Evidence: Agent analysis matches human analysis 90%+ of the time
  ▼
Tier 1 (RECOMMEND)
  │ Evidence: Agent recommendations accepted by humans 80%+ of the time
  ▼
Tier 2 (DRAFT)
  │ Evidence: Agent PRs merged without modification 70%+ of the time
  ▼
Tier 3 (SANDBOX EXECUTE)
  │ Evidence: Sandbox runs succeed without human intervention 95%+
  ▼
Tier 4 (PROD WITH GATES)
  │ Only for well-understood, low-blast-radius operations
  │ Always with human approval gate
```

---

## Compliance Mapping

### NIST AI Risk Management Framework（AI RMF）

| NIST AI RMF Function | What It Means | How This Guide Addresses It |
|----------------------|---------------|---------------------------|
| **GOVERN** | 建立 AI risk governance | Autonomy tiers、policy engine、org-level policies（Ch 8） |
| **MAP** | 在上下文中理解 AI risks | 上述 risk matrix、agent-specific threat modeling |
| **MEASURE** | 评估并跟踪风险 | Observability、action trails、trajectory tests（Ch 9, 12） |
| **MANAGE** | 处置并持续监控风险 | Guardrails、sandboxing、credential isolation、notifications（Ch 4-8, 10） |

### OWASP LLM Top 10 Coverage

| OWASP Risk | Relevant Chapters |
|-----------|-------------------|
| LLM01: Prompt Injection | Ch 4（Sandbox）, Ch 8（Policy）, Ch 12（Testing） |
| LLM02: Insecure Output Handling | Ch 7（PR validation）, Ch 9（Redaction） |
| LLM03: Training Data Poisoning | 不在本文范围内（使用受信任的 LLM providers） |
| LLM04: Model Denial of Service | Ch 8（Budget limits）, Ch 2（Queue management） |
| LLM05: Supply Chain Vulnerabilities | Ch 3（Skill system，不信任未知 skills） |
| LLM06: Sensitive Information Disclosure | Ch 5（Credentials）, Ch 9（Redaction） |
| LLM07: Insecure Plugin Design | Ch 3（Skills 作为 files，typed interfaces） |
| LLM08: Excessive Agency | Ch 8（Tool restrictions，autonomy tiers） |
| LLM09: Overreliance | Ch 7（Human review）, Ch 8（HITL checkpoints） |
| LLM10: Model Theft | 不在本文范围内（使用托管型 LLM APIs） |

### SOC 2 Considerations

| SOC 2 Criteria | Agent-Relevant Control | Implementation |
|---------------|----------------------|----------------|
| CC6.1 - Logical access | Agent credential management | Short-lived tokens、scoped permissions（Ch 5） |
| CC6.3 - Authorized access | Tool allow/deny lists | Policy engine、tier-based restrictions（Ch 8） |
| CC7.2 - Monitoring | Agent activity monitoring | Action trails、dashboards、alerts（Ch 9, 10） |
| CC8.1 - Change management | PR-based change control | Agent changes 通过标准 CI/CD 流程落地（Ch 7） |

---

## Go-Live Checklist

### Phase 1：Foundation（Week 1-2）

```
INFRASTRUCTURE
[ ] Task queue deployed and tested (Redis Streams / SQS / etc.)
[ ] Worker deployment pipeline established
[ ] Sandbox containers built with IaC tools pre-installed
[ ] Metadata endpoint blocked in sandbox networking
[ ] Credential broker and tool access layer running

SECURITY
[ ] Credential broker implemented and tested
[ ] Short-lived token generation for each cloud provider
[ ] Secret storage configured (Vault / KMS / Key Vault)
[ ] Network egress rules applied to sandbox

OBSERVABILITY
[ ] OpenTelemetry instrumentation in place
[ ] Action trail event emission working
[ ] Log redaction configured
[ ] Basic dashboard (active sessions, success rate, queue depth)
```

### Phase 2：First Agent（Week 3-4）

```
AGENT CONFIGURATION
[ ] System prompt with hard rules defined
[ ] Effective agent/subagent definitions resolved by layer and logged
[ ] Skills/tools defined and tested
[ ] Tool allow/deny list configured
[ ] Max iteration and budget limits set

CHANGE CONTROL
[ ] PR creation workflow tested end-to-end
[ ] CI pipeline triggers from agent PRs
[ ] Branch naming convention established
[ ] PR body template includes validation results

TESTING
[ ] Unit tests for all skills pass
[ ] At least 3 trajectory tests covering happy path
[ ] At least 2 adversarial tests (prompt injection)
[ ] Manual end-to-end test with real infrastructure
```

### Phase 3：Autonomous Operations（Week 5-6）

```
SCHEDULING
[ ] Cron/EventBridge/Timer configured for recurring scans
[ ] Staggered dispatch prevents queue flooding
[ ] Missed run catch-up mechanism in place

NOTIFICATIONS
[ ] Slack/Teams integration configured
[ ] Notification routing rules defined
[ ] Escalation chain for critical failures
[ ] Daily digest scheduled

MONITORING
[ ] Stuck/stalled task detection active
[ ] Unacknowledged message recovery on worker startup
[ ] Alert on agent failure rate > threshold
[ ] Alert on queue depth > threshold
[ ] Alert on token usage anomalies
```

### Phase 4：Scale（Week 7+）

```
MULTI-AGENT
[ ] Multiple agent types configured (remediation, drift, PR review)
[ ] Task type routing to specialized worker pools
[ ] Concurrent session handling tested under load

SESSION MANAGEMENT
[ ] Session persistence working (git bundles + session state)
[ ] Session resume after worker restart tested
[ ] Human-in-the-loop input flow tested end-to-end
[ ] Message queuing for busy agents

GOVERNANCE
[ ] Organization-level policies defined and injected
[ ] Managed agent definitions reviewed; project/user definitions cannot expand beyond enterprise policy
[ ] Autonomy tiers assigned per use case
[ ] Monthly action trail review process established
[ ] Incident response plan for agent failures documented
```

---

## 什么时候不应该使用 Agent

并不是每一个基础设施任务都需要 AI agent。在以下场景中，应该使用更简单的自动化：

| Scenario | Better Approach |
|----------|----------------|
| 每次修复都相同，没有变化 | Shell script / CI pipeline |
| 简单的资源 provisioning | Terraform modules / CDK constructs |
| Alert → restart service | PagerDuty automation / Lambda |
| Log rotation / cleanup | Cron job |
| Certificate renewal | cert-manager / ACM |

**适合使用 agents 的情况**：任务需要理解上下文、做判断，或适应变化。如果你能用一个 `if/else` 覆盖所有情况，那你就不需要 agent。

---

## Architecture Decision Record Template

在为 agent system 做架构决策时，应该把它们记录下来：

```markdown
# ADR-001: Task Queue Technology

## Status
Accepted

## Context
We need a task queue for dispatching agent work to stateless workers.
Requirements: consumer groups, message persistence, real-time output streaming.

## Decision
Redis Streams with consumer groups for dispatch, separate streams for output.

## Alternatives Considered
- **BullMQ**: Good Node.js integration but tied to Redis anyway
- **AWS SQS**: No consumer groups; would need additional pub/sub for streaming
- **Temporal**: Too heavy for our current scale; might revisit at 100+ concurrent agents

## Consequences
- Need Redis 5.0+ in production
- Must handle PEL recovery on worker startup
- Stream trimming needed to prevent unbounded memory growth
```

---

## 总结

基础设施 agent system 的六个 plane：

1. **Ingestion**：工作如何进入系统（webhooks、schedules、chat、APIs）
2. **Policy**：agents 被允许做什么（tiers、tool lists、budgets）
3. **Execution**：agents 如何在隔离环境中运行（sandboxed containers、stateless workers）
4. **Integration**：agents 如何访问外部系统（short-lived credentials、typed skills）
5. **Change Control**：变更如何落地（PRs、validation loops、CI/CD）
6. **Observability**：你如何看到发生了什么（action trails、OTel、notifications）

如果这些 plane 设计错误，你就会得到报告中的那些 incident：恶意 skills、credential theft、失控成本，以及 enterprise 级封禁。

---

*Built by the team at [Cloudgeni](https://cloudgeni.ai) — Scale your infrastructure team. With Agents. Safely.*
