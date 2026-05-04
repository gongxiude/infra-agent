# 第 9 章：Observability 与 Audit

> OpenTelemetry、action trails、correlation IDs，以及 agent failures 的调试。

---

## 为什么 Agent Observability 不同

传统 observability 回答的是：“我的 service 健康吗？”
Agent observability 必须回答：**“agent 为什么会这么做？”**

当一个 agent 创建了一个会破坏 staging 的 PR 时，你需要回溯以下内容：
- 是什么 prompt 触发了这个 agent？
- 它组装了什么 context？
- 它调用了哪些 tools，参数是什么？
- 这些 tools 返回了什么？
- 做出了哪些 policy decisions？
- 发放了哪些 credentials？

没有这条 trail，agent failures 就是黑盒。

---

## Three Pillars + Action Trails

```
Traditional Observability          Agent Observability
─────────────────────              ─────────────────────
Logs                               Logs
Metrics                            Metrics
Traces                             Traces
                                   + Action Trails ← NEW
```

**Action trails** 是 agent 所做一切的结构化 event logs，与 LLM conversation 分离。它们可查询、可审计，并且不依赖解析 chat transcripts。

---

## OpenTelemetry Attribute Schema

为所有 agent spans 定义一致的 attribute namespace。选择一个 prefix（例如 `agent.` 或你的产品名）并坚持使用。下面是一组按类别组织的推荐 attributes：

| Category | Attribute | Example Value |
|----------|-----------|---------------|
| **Correlation** | `agent.request.id` | `req-abc123` |
| | `agent.correlation.id` | `corr-xyz789` |
| | `agent.traceparent` | W3C traceparent |
| | `agent.tracestate` | W3C tracestate |
| **Agent context** | `agent.session.id` | `sess-456` |
| | `agent.run.id` | `run-789` |
| | `agent.type` | `remediation` |
| | `agent.definition.source` | `managed` |
| | `agent.definition.version` | Git SHA or policy version |
| | `agent.permission.mode` | `read-only` / `validate` |
| | `agent.organization.id` | `org-123` |
| **Task context** | `agent.task.type` | `compliance-fix` |
| | `agent.task.priority` | `high` |
| | `agent.trigger.source` | `schedule` |
| **Execution** | `agent.iteration.count` | `3` |
| | `agent.tokens.input` | `12500` |
| | `agent.tokens.output` | `3200` |
| | `agent.tool_calls.count` | `8` |
| **Performance** | `agent.perf.repo_clone_ms` | `4500` |
| | `agent.perf.pipeline_wait_ms` | `62000` |
| | `agent.perf.total_duration_ms` | `180000` |
| **Queue** | `agent.queue.depth` | `12` |
| | `agent.queue.wait_ms` | `3200` |
| **Credentials** | `agent.credential.scope` | `management.azure.com` |
| | `agent.credential.expires_at` | ISO timestamp |

关键原则是：每个 span 都应携带足够的 context，能够回答 “是哪个 agent、哪个 task、哪个 organization、耗时多久、消耗多少？”

### 跨异步边界传播 Trace Context

长时间运行的 agent 会跨越 queues、streams、RPC boundaries、SSE channels 和 resume flows。Correlation IDs 有帮助，但单靠它们还不够。你必须传播 **W3C trace context**（`traceparent`、`tracestate`、`baggage`），覆盖以下位置：

- task dispatch messages
- task output events
- RPC requests/responses
- action trail records
- 当 session 在新 worker 上恢复时持久化的 run metadata

没有这一步，你可以观察每个组件，但仍然无法端到端重建一次逻辑上的完整 run。

### Instrument Agent Lifecycle

为 agent execution 的每个阶段创建嵌套 spans。这样你会得到一棵 trace tree，精确展示时间花在了哪里：

```typescript
import { trace, SpanStatusCode } from '@opentelemetry/api';

const tracer = trace.getTracer('agent-worker');

async function processAgentTask(task: AgentTask) {
  return tracer.startActiveSpan('agent.process_task', async (span) => {
    span.setAttributes({
      'agent.session.id': task.sessionId,
      'agent.type': task.agentType,
      'agent.task.type': task.type,
      'agent.trigger.source': task.trigger.source,
    });

    try {
      // Clone repository
      await tracer.startActiveSpan('agent.clone_repo', async (cloneSpan) => {
        const startMs = Date.now();
        await cloneRepository(task.repository);
        cloneSpan.setAttribute('agent.perf.repo_clone_ms', Date.now() - startMs);
        cloneSpan.end();
      });

      // Run agent
      const result = await tracer.startActiveSpan('agent.run', async (runSpan) => {
        const result = await executeAgent(task);
        runSpan.setAttributes({
          'agent.iteration.count': result.iterations,
          'agent.tokens.input': result.inputTokens,
          'agent.tokens.output': result.outputTokens,
          'agent.tool_calls.count': result.toolCalls,
        });
        runSpan.end();
        return result;
      });

      span.setStatus({ code: SpanStatusCode.OK });
      return result;
    } catch (error) {
      span.setStatus({ code: SpanStatusCode.ERROR, message: error.message });
      span.recordException(error);
      throw error;
    } finally {
      span.end();
    }
  });
}
```

---

## Action Trail Events

发往专用 stream 的结构化 events，不与 LLM conversation 混在一起：

```typescript
interface ActionTrailEvent {
  timestamp: string;
  sessionId: string;
  runId: string;
  correlationId: string;
  agentDefinition?: {
    name: string;
    source: 'managed' | 'project' | 'user' | 'plugin' | 'runtime';
    version?: string;
    tools?: string[];
    permissionMode?: string;
  };
  traceContext?: {
    traceparent?: string;
    tracestate?: string;
    baggage?: string;
  };
  type:
    | 'tool_call'
    | 'tool_result'
    | 'credential_issued'
    | 'policy_evaluated'
    | 'pipeline_triggered'
    | 'pr_created'
    | 'human_input_requested'
    | 'human_input_received'
    | 'state_restored'
    | 'run_resumed'
    | 'orphan_recovered'
    | 'policy_denied'
    | 'error'
    | 'budget_warning';
  data: Record<string, unknown>;
}

// Emit action trail events
async function emitActionTrail(event: ActionTrailEvent) {
  // 1. Redis stream (real-time consumption)
  await redis.xadd(`action-trail:${event.sessionId}`, '*', {
    type: event.type,
    data: JSON.stringify(event.data),
    correlationId: event.correlationId,
    timestamp: event.timestamp,
  });

  // 2. Structured log (long-term storage)
  logger.info({
    msg: `action_trail:${event.type}`,
    ...event,
  });

  // 3. OpenTelemetry span event (trace correlation)
  const span = trace.getActiveSpan();
  if (span) {
    span.addEvent(event.type, event.data);
  }
}
```

### Remediation Task 的示例 Trail

```json
[
  { "type": "tool_call", "data": { "tool": "read-file", "args": { "path": "main.tf" } } },
  { "type": "tool_result", "data": { "tool": "read-file", "size": 2340 } },
  { "type": "tool_call", "data": { "tool": "write-file", "args": { "path": "main.tf" } } },
  { "type": "credential_issued", "data": { "scope": "management.azure.com", "ttl": 3600 } },
  { "type": "pipeline_triggered", "data": { "pipelineId": "p-123", "type": "PLAN" } },
  { "type": "tool_result", "data": { "pipeline": "success", "drift": 0 } },
  { "type": "pr_created", "data": { "url": "https://github.com/org/repo/pull/42", "branch": "agent/fix-123" } }
]
```

---

## Failure Taxonomy 与 Recovery Events

不要只停留在 “success” 和 “failed”。你需要 instrument run 为什么结束，以及是否发生 recovery。

| Category | 含义 | 重要性 |
|----------|------|--------|
| **AUTH_EXPIRED** | Token/session 过期，并尝试过 refresh | 将 credential churn 与真实 task failure 区分开 |
| **TRANSIENT** | 网络、429、provider 临时问题 | 展示 retry 压力与 queue amplification |
| **PERMANENT** | 无效请求、缺少权限、repo state 异常 | 指示 agent 或 configuration defect |
| **TIMEOUT** | Agent 或外部 pipeline 超过 budget | 驱动 budget 与 watchdog tuning |
| **WAITING_INPUT** | Run 在 human checkpoint 上暂停 | 对 UX latency 和 abandonment tracking 很重要 |
| **RECOVERED** | Worker 崩溃但 run 成功 resumed/restored | 证明 durability design 在工作 |

对 `waiting_input_entered`、`waiting_input_timed_out`、`state_restored`、`orphan_recovered` 这类状态转移发出显式 events。Recovery 应在 traces 和 dashboards 中可见，而不是通过日志空洞来推断。

---

## Observability Stack Alternatives

### Option 1: OpenTelemetry + Grafana Stack（Self-Hosted）

```yaml
# docker-compose.yml — observability stack
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:latest
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317"   # gRPC
      - "4318:4318"   # HTTP

  tempo:
    image: grafana/tempo:latest
    # Trace storage

  loki:
    image: grafana/loki:latest
    # Log aggregation

  prometheus:
    image: prom/prometheus:latest
    # Metrics

  grafana:
    image: grafana/grafana:latest
    # Dashboards
    ports:
      - "3001:3000"
```

```yaml
# otel-collector-config.yaml
receivers:
  otlp:
    protocols:
      grpc: { endpoint: "0.0.0.0:4317" }
      http: { endpoint: "0.0.0.0:4318" }

processors:
  batch:
    timeout: 5s

exporters:
  otlphttp/tempo:
    endpoint: http://tempo:4318
  loki:
    endpoint: http://loki:3100/loki/api/v1/push
  prometheus:
    endpoint: "0.0.0.0:8889"

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/tempo]
    logs:
      receivers: [otlp]
      processors: [batch]
      exporters: [loki]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

### Option 2: Datadog

```typescript
import tracer from 'dd-trace';
tracer.init({ service: 'infra-agent-worker' });

// Datadog auto-instruments most frameworks
// Custom spans for agent-specific operations
const span = tracer.startSpan('agent.run_task');
span.setTag('agent.slug', task.agentSlug);
// ...
span.finish();
```

### Option 3: Dash0 / Grafana Cloud / New Relic

这些都原生支持 OpenTelemetry。使用 OTel SDK 做一次 instrumentation，然后导出到任意 backend 即可。

---

## Dashboard Essentials

### Agent Operations Dashboard

| Panel | Query (PromQL) | 目的 |
|-------|---------------|------|
| Active sessions | `count(agent_sessions_active)` | 当前负载 |
| Avg completion time | `histogram_quantile(0.95, agent_task_duration_seconds_bucket)` | 性能 |
| Success rate | `rate(agent_tasks_total{status="success"}[1h]) / rate(agent_tasks_total[1h])` | 可靠性 |
| Token usage | `sum(rate(agent_tokens_total[1h])) by (agent_type)` | 成本跟踪 |
| Queue depth | `agent_queue_depth` | 积压 |
| PRs created | `increase(agent_prs_created_total[24h])` | 输出 |
| Credential issuances | `rate(agent_credentials_issued_total[1h])` | 安全审计 |
| Waiting-input age | `max(agent_waiting_input_age_seconds)` | 人工瓶颈 |
| Orphan recoveries | `increase(agent_orphan_recoveries_total[24h])` | 耐久性健康度 |
| Policy denials | `increase(agent_policy_denials_total[24h])` | Guardrail 压力 |

---

## Log Redaction

Agent logs 经常包含敏感数据（resource IDs、config values、带 secrets 的 error messages）。默认应进行 redact：

```typescript
const REDACTION_PATTERNS = [
  /(?:api[_-]?key|token|secret|password|credential)["\s:=]+["']?([a-zA-Z0-9+/=_-]{20,})["']?/gi,
  /AKIA[0-9A-Z]{16}/g,                          // AWS Access Key
  /(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36}/g, // GitHub tokens
  /eyJ[A-Za-z0-9-_]+\.eyJ[A-Za-z0-9-_]+/g,     // JWT tokens
];

function redactSensitive(text: string): string {
  let redacted = text;
  for (const pattern of REDACTION_PATTERNS) {
    redacted = redacted.replace(pattern, '[REDACTED]');
  }
  return redacted;
}
```

---

## 下一章

[第 10 章：Autonomous Operations 与 Notifications →](./10-autonomy-notifications-zh.md)
