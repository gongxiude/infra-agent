# 第 6 章：The Data Plane，给 Agents 提供 Context

> 为什么没有预构建 context 的 agents 会把 token 浪费在重新发现你已经知道的信息上，以及如何把基础设施知识序列化为 agents 真正可用的格式。

---

## 问题：Discovery 很昂贵

让一个基础设施 agent 去“修复 production 中未加密的 S3 bucket”。如果没有预构建 context，事情会是这样：

```
Agent: calls aws s3api list-buckets                     # 200+ buckets, 15s
Agent: for each bucket, calls get-bucket-encryption      # 200 API calls, 90s
Agent: for each unencrypted, calls get-bucket-tagging    # more API calls
Agent: cross-references with terraform state             # terraform state pull, 30s
Agent: reads tf files to find the resource address       # grep across repo
Agent: finally has enough context to write a fix         # 3+ minutes burned
```

这相当于在 cloud 世界里对 10,000 个文件运行 `grep`。在人类规模下（一个 bucket）它还能工作。但在基础设施规模下（数百个资源、多个 account、四种 cloud）它就会崩溃。

成本会叠加：
- **API rate limits**，cloud provider 在几百次调用后就会开始限流
- **Token 浪费**，LLM 要处理成页的 JSON，只为了提取其中三个字段
- **Latency**，在 agent 开始真正工作之前，就要先花几分钟做 API calls
- **没有 relationships**，比如这个 subnet 属于哪个 VPC？Agent 每次都得从头发现
- **没有 organizational context**，谁拥有这个资源？是否有相关 ADR？Agent 无法知道

解决办法是：不要让 agents 去重新发现你已经知道的东西。构建一个 data plane，在 agent 需要这些信息之前，就先收集、关联并序列化基础设施知识。

---

## Agents 需要知道什么

基础设施 agents 不仅需要 cloud resource 列表。它们需要横跨多个系统的分层 context：

```
┌──────────────────────────────────────────────────────────┐
│                    CONTEXT LAYERS                        │
│                                                          │
│  Layer 1: Cloud Resources                                │
│  ┌────────────────────────────────────────────────────┐  │
│  │ What exists? EC2, S3, VPC, VNet, GKE, ...          │  │
│  │ What state is it in? Config, tags, status          │  │
│  │ How do resources relate? VPC→Subnet→Instance       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Layer 2: Infrastructure as Code                         │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Which resources are managed by IaC?                │  │
│  │ What's the Terraform address? Which repo/file?     │  │
│  │ Which resources are unmanaged (ClickOps)?          │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Layer 3: Security & Compliance                          │
│  ┌────────────────────────────────────────────────────┐  │
│  │ What findings exist? Which resource is affected?   │  │
│  │ What framework? CIS, SOC2, ISO 27001               │  │
│  │ What's the remediation recommendation?             │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Layer 4: Cost & Usage                                   │
│  ┌────────────────────────────────────────────────────┐  │
│  │ How much does this resource cost?                  │  │
│  │ Is it underutilized? Rightsizing candidates?       │  │
│  └────────────────────────────────────────────────────┘  │
│                                                          │
│  Layer 5: Organizational Knowledge                       │
│  ┌────────────────────────────────────────────────────┐  │
│  │ Who owns this? Which team, which service?          │  │
│  │ What are the naming conventions?                   │  │
│  │ Are there ADRs, runbooks, past incidents?          │  │
│  └────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

拥有这五层 context 的 agent，可以把“修复未加密的 bucket”在几秒内转化成“这里有一个 PR，它会在 `modules/storage/main.tf` 中为 `aws_s3_bucket.prod_logs` 增加 SSE-KMS，使用同一个 account 中现有的 KMS key，并遵循 Payments 团队的 encryption standard”。

只有 Layer 1 的 agent，写出的修复可能在技术上正确，但在组织语义上错误，而且还要花数分钟才能走到那一步。

---

## 核心模式：Scan、Correlate、Serialize

无论具体实现如何，每个 data plane 都遵循相同的模式：

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   COLLECT    │────▶│    STORE     │────▶│  CORRELATE   │────▶│  SERIALIZE   │
│              │     │              │     │              │     │              │
│ Cloud APIs   │     │ Normalized   │     │ Cloud ↔ IaC  │     │ Markdown for │
│ IaC state    │     │ resources,   │     │ Cloud ↔ Sec  │     │ LLM context  │
│ Compliance   │     │ findings,    │     │ Resource ↔   │     │              │
│ Cost data    │     │ cost data    │     │ Resource     │     │ JSON for     │
│ Docs/wikis   │     │              │     │              │     │ skill APIs   │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

### 步骤 1：Collect

按计划扫描 cloud accounts，并从外部系统拉取数据：

| Data Source | 如何收集 | 频率 |
|------------|---------|------|
| Cloud resources | Provider APIs（describe/list calls）或 asset inventory 工具 | 每 1-6 小时 |
| IaC state | 解析 Terraform state files、Bicep what-if output | 在 git push 时（webhook） |
| Compliance findings | Security scanners（Prowler、Checkov、Trivy、provider-native） | 每晚或按需 |
| Cost data | Cloud billing APIs（Cost Explorer、Cost Management） | 每日 |
| Resource relationships | 在 cloud resource scan 期间提取 | 随 resource scan 一起 |
| Documentation | Wiki APIs（Confluence、Notion）、git repos（READMEs、ADRs） | 每日或变更时 |

### 步骤 2：使用 Normalized Model 进行存储

每个 cloud resource，无论来自哪个 provider，都应被规范化为统一结构。具体细节取决于你的实现，但关键字段包括：

```typescript
// Core identity — same across all providers
interface NormalizedResource {
  providerResourceId: string;    // AWS ARN, Azure Resource ID, GCP self-link
  providerResourceType: string;  // 'AWS_S3_BUCKET', 'Microsoft.Storage/storageAccounts'
  providerResourceName: string;  // Human-readable name
  provider: string;              // 'AWS', 'AZURE', 'GCP', 'OCI'
  region: string;

  // Full configuration as JSON — expensive to scan, cheap to query
  properties: Record<string, unknown>;
  tags: Record<string, string>;
  status: string;

  // IaC correlation
  managedBy?: {
    tool: string;              // 'terraform', 'bicep', 'pulumi'
    address: string;           // 'aws_s3_bucket.prod_logs'
    repository: string;        // 'github.com/org/infra'
    filePath: string;          // 'modules/storage/main.tf'
  };
}
```

`properties` 字段至关重要，它存储 provider 返回的完整 resource configuration。Agent 可以从数据库查询中读取它，而不是发起一次 live API call。

### 步骤 3：Correlate

Correlation 会把平铺的 resource 列表转化成可执行的 context：

**Cloud ↔ IaC：** 通过比较 provider resource IDs（ARNs、Azure Resource IDs）与 IaC state files，把 cloud resources 映射到管理它们的代码。这能告诉 agent **去哪里修复问题**，即哪个 repo、哪个文件、哪个 Terraform address。没有 IaC match 的 resources 就是 unmanaged（手工创建或通过 ClickOps 创建），agent 需要以不同方式处理它们，比如导入 IaC 或建议删除。

**Cloud ↔ Compliance：** Compliance findings 通过 provider ID 引用 cloud resources。把它们关联起来，agent 就能一步从“HIGH severity finding”跳转到“这个 S3 bucket，在这个 repo 中，位于这个 Terraform address”。

**Resource ↔ Resource：** 基础设施本质上是一张 graph。VPC 包含 subnets，subnets 受 security groups 保护，instances 连接到 subnets。把这些关系存成 edge table，agent 就能遍历 graph：“什么连接到了这个 VPC？”会直接返回 subnets、route tables、security groups 和 instances，而无需任何 API calls。

### 步骤 4：为 LLM Consumption 做 Serialize

这是大多数实现会跳过的一步，但它比你想象的更重要。

原始 cloud API responses 是冗长的 JSON，里面有嵌套结构、pagination tokens、provider-specific quirks，以及一堆 agent 根本不需要的字段。一个 S3 bucket 的完整 API response 大约有 2,000 tokens，而 agent 真正需要的五个字段只占 50 tokens 左右。

**序列化成 markdown，而不是 JSON：**

```typescript
function serializeResourceForAgent(resource: NormalizedResource): string {
  const lines: string[] = [
    `#### ${resource.providerResourceName}`,
    `- **Type:** ${resource.providerResourceType}`,
    `- **Provider:** ${resource.provider} / ${resource.region}`,
    `- **Resource ID:** ${resource.providerResourceId}`,
  ];

  if (Object.keys(resource.tags).length > 0) {
    lines.push(`- **Tags:** ${JSON.stringify(resource.tags)}`);
  }

  if (resource.managedBy) {
    lines.push(`- **IaC:** \`${resource.managedBy.address}\` in ${resource.managedBy.repository}`);
  } else {
    lines.push(`- **IaC:** Not managed (no Terraform/Bicep resource found)`);
  }

  return lines.join('\n');
}
```

为什么 markdown 优于 JSON：
- **每条事实需要的 tokens 更少**，没有大括号、中括号和引号字符
- **Headers 帮助模型导航**，`#### prod-logs-bucket` 比嵌套 JSON key 更容易解析
- **可选择性裁剪**，只包含 agent 需要的信息，而不是完整 cloud API response
- **更容易截断**，即使你把 context 限制在 2,000 个字符内，它仍然自然可读

同样的原则适用于所有数据类型：compliance findings、drift diffs、cost reports。在把它们注入 agent context 之前，先把每一种都序列化为紧凑、可读的格式。

```typescript
function serializeFindingForAgent(finding: ComplianceFinding): string {
  return [
    `### ${finding.title}`,
    `**Severity:** ${finding.severity} | **Framework:** ${finding.framework} (${finding.controlId})`,
    `**Resource:** ${finding.resourceId}`,
    `**Remediation:** ${finding.remediationRecommendation}`,
  ].join('\n');
}
```

---

### 步骤 5：保留 Ground Truth 和 Proposal State

Data plane 不应该只回答“存在哪些资源？”。它还应保留：

- **Discovered truth**，cloud 和 scanners 所观察到的真实状态
- **Workspace ground truth**，agent 开始工作时文件内容和 state 的精确快照
- **Proposed truth**，agent 打算实施的结构化变更

第三类最容易被忽略。对于基础设施 agents，proposed truth 往往包括：

- 计划中的 resources 和 relationships
- create/delete 带来的成本变化
- validation artifacts（`plan`、`what-if`、policy checks）
- 即使 PR 还不存在，也要保留已对齐的 file-change snapshots

这些内容应该独立于原始 chat transcript 持久化保存。它们能支撑更好的 UI、更可靠的 resume 行为，以及更强的 review flows：

- graph overlays，而不是原始 JSON blobs
- merge 前的 cost previews
- agent 通过 tools 修改文件时的 diff reconciliation
- worker 重启之后的 deterministic recovery

并不是所有有价值的 context 都应该放进 prompt。有些 context 应该在 model 外部保持 **可查询**、**可渲染**、**可版本化**。

---

## 为什么这会影响 Agent 质量

预构建 context 不只是节省 tokens，它会改变 agent 的能力边界。

### 没有 data plane 时

Agent 是盲的。每个 task 都从 discovery 开始。Agent 把大部分 token budget 和 iteration 次数花在**寻找信息**，而不是**修复问题**。它只能处理那些能通过 CLI tools 发现的资源，这意味着：
- 它会错过 relationships（不知道 subnet 归属哪个 security group）
- 它无法跨 accounts 或 regions 进行比较
- 它不知道一个 resource 是由 IaC 管理，还是手工创建
- 它没有 organizational context（team ownership、naming conventions、past incidents）

### 有 data plane 时

Agent 一开始就拥有所需的一切。它知道 resource 长什么样、它在代码中哪里定义、有哪些 compliance findings 影响它，以及哪些 related resources 已经存在。这意味着：
- **更少 iterations**，agent 第一次就能修对，而不是花 5 轮去补齐 context
- **更好的修复质量**，agent 能看到周边基础设施，因此能写出符合现有模式的代码
- **更安全的决策**，agent 知道一个 resource 是否跨环境共享，因此会更谨慎地行动
- **组织语义感知**，agent 会遵循 naming conventions、尊重 ADR，并参考过去的 remediation 模式

这种差异是可量化的。拥有预构建 context 的 agent，通常在 1-2 次 tool calls 内就能解决 finding。没有它，同样的 agent 往往需要 5-10 次 tool calls，而且修复质量更低。

---

## Resource Relationships：图结构

平铺的 resource 列表会遗漏最重要的 context：**资源彼此如何关联**。

一个修复 security group rule 的 agent，需要知道它后面挂着哪些 VMs。一个修复 storage encryption finding 的 agent，需要知道同一个 account 中是否已经存在合适的 KMS key。

### Relationship Types

定义一套资源之间的有向边词汇表：

```
CONTAINS      VPC → Subnet, Resource Group → VM
BELONGS_TO    Subnet → VPC
SECURED_BY    NIC → NSG, Subnet → NSG
ROUTES_VIA    Subnet → Route Table
CONNECTED_TO  NIC → Subnet, Instance → VPC
PEERED_WITH   VPC → VPC
ATTACHED_TO   NIC → VM, Disk → VM
USES          Container App → Container Registry
ENCRYPTED_BY  Storage Account → Key Vault Key
HOSTS         App Service Plan → Web App
```

把这些关系存成数据库中的 edge table：`source_id`、`target_id`、`relationship_type`。不需要 graph database，只要一个包含 `source_id`、`target_id` 和 `type` 的简单 adjacency list，就足以高效处理数千个 resources。PostgreSQL recursive CTEs 可以遍历 2-3 跳，这已经覆盖了大多数 agent use cases。

### 为什么 agents 需要 graph

当一个 agent 收到 finding“`prod-logs` S3 bucket 未加密”时，它需要：
1. 找到这个 bucket（Layer 1）
2. 找到它的 IaC address（Layer 2）
3. 检查同一个 account 中是否已经存在 KMS key（graph traversal）
4. 如果有，就引用它；如果没有，就创建一个

如果没有 graph，第 3 步就需要额外的 API calls。有了 graph，它只是一条数据库查询：“给我显示这个 account 中所有类型为 `AWS_KMS_KEY` 的 resources。”

---

## Organizational Knowledge

基础设施 agents 不仅需要 cloud data。它们还需要 organizational context，否则它们会产出技术上正确、但组织语义上错误的结果。

一个修复 `prod-payments-vpc` compliance finding 的 agent 应该知道：
- 这个 VPC 属于 Payments 团队
- Payments 团队使用特定的 resource naming convention
- 有一份 ADR 解释了为什么这个 VPC 必须做 network isolation
- 上个月修复过一个类似 finding，这里是当时的处理方式

### Sources

| Source | 提供什么 | 如何摄取 |
|--------|---------|---------|
| **Cloud resource tags** | Team ownership、environment、cost center | 在 cloud scan 时提取 |
| **Git repositories** | IaC code、READMEs、ADRs、module docs | 扫描时 clone 并建立索引 |
| **Wiki/docs**（Confluence、Notion） | Architecture docs、runbooks、naming conventions | 定时通过 API 同步 |
| **Service catalogs**（Backstage、ServiceNow） | Service ownership、dependencies、SLOs | API sync |
| **Incident management**（PagerDuty、OpsGenie） | 按 service/resource 聚合的 past incidents | Webhook 或 API sync |
| **Past agent sessions** | 以往决策、reasoning、patterns | 已在 session store 中 |
| **Custom policies** | 用自然语言定义的组织特有规则 | 由管理员撰写并存入 DB |

### Ingestion Tiers

并不是所有知识都具有相同的结构化程度：

```
Tier 1: Structured data  → Cloud resources, IaC state, compliance findings, cost data
                           Store in database with typed columns.

Tier 2: Semi-structured   → READMEs, ADRs, wiki pages, module docs
                           Parse to text, extract metadata, index for search.

Tier 3: Unstructured       → Architecture diagrams, whiteboard photos, meeting recordings
                           Use vision models for images, speech-to-text for audio.
                           Convert to text and index alongside Tier 2.
```

从 Tier 1 开始，它以最少的工程投入为 agents 提供最高价值。等到 agents 开始产出组织语义错误的修复时，再加入 Tier 2。只有当你确实拥有大量关键的非结构化知识会影响 agent 决策时，才考虑加入 Tier 3。

### 让知识可访问

两种方法，而且并不互斥：

**在 dispatch 时注入**，当 task 被 dispatch 时，系统预先拉取相关 context，并把它放入 agent 的 initial prompt。这适用于聚焦型任务（“修复这个 finding”），因为你知道 agent 需要什么 context。

**提供可查询的 skill APIs**，给 agent 提供 skills，让它在需要时自己检索和拉取 context。这适用于探索型任务（“解释一下这套基础设施”），因为由 agent 自己决定查什么。

实践中通常两者都要用：先把明显需要的 context 注入进去，再给 agent 能力，让它在需要时自行拉取更多。

---

## 向 Agents 暴露数据

直接暴露原始数据库访问既危险，又缺乏结构。应通过 typed APIs（tools、skills 或 MCP resources）来暴露 data plane，并只返回 agent 真正需要的数据。示例查询模式：

```typescript
// Cloud resources — filtered, paginated, pre-serialized
const resources = await queryResources({
  provider: 'AWS',
  resourceType: 'AWS_S3_BUCKET',
  managedByIaC: false,          // Only unmanaged resources
  search: 'prod',
});

// Compliance findings — linked to affected resources
const findings = await queryFindings({
  severity: 'HIGH',
  status: 'OPEN',
  resourceType: 'AWS_S3_BUCKET',
});

// Resource relationships — graph traversal
const graph = await queryResourceGraph({
  resourceId: 'arn:aws:ec2:us-east-1:123:vpc/vpc-abc',
  depth: 2,
});
// Returns: VPC → Subnets → Instances, VPC → IGW, VPC → Security Groups

// Organizational knowledge — searchable
const docs = await searchKnowledge({
  query: 'VPC isolation policy payments team',
  sources: ['wiki', 'adr', 'policy'],
});
```

Agent 接收到的是结构化、预格式化的 responses。没有原始 CLI output，没有 pagination，也没有 rate limiting。至于你是把这些能力实现成 tool functions、MCP resources，还是 REST endpoints，那只是实现选择。关键点是：对每一层 data，都通过 typed、scoped 的方式提供访问。

---

## Agents 如何消费数据：从 Context Injection 到 RAG

你已经收集、关联并序列化了基础设施数据。接下来的问题是：**这些数据究竟如何进入 agent 的 context？** 这里有一条从简单到复杂的光谱，正确选择取决于数据量和查询可预测性。

### Level 1：Direct Context Injection（小数据、已知查询）

对于那些你在任务一开始就知道 agent 需要什么的聚焦任务，直接把数据放进 prompt 即可。不需要 retrieval system。

```
System prompt:
  "You are a compliance remediation agent."

Injected context:
  ## Finding
  S3 bucket `prod-logs` missing server-side encryption.
  Severity: HIGH | Framework: CIS AWS v3.0 | Control: 2.1.1

  ## Affected Resource
  - Type: AWS_S3_BUCKET
  - Region: us-east-1
  - IaC: `aws_s3_bucket.prod_logs` in modules/storage/main.tf

  ## Related Resources
  - KMS Key `alias/infra-key` exists in same account (arn:aws:kms:us-east-1:...)
  - Bucket policy attached, no public access

  ## Organization Policies
  - All S3 buckets MUST use SSE-KMS with alias/infra-key
  - Never disable encryption, even temporarily

User prompt:
  "Fix this finding."
```

这种方式适用于：
- 数据可以轻松放进 context（约 2,000-10,000 tokens）
- 你能在 agent 开始前预测它需要什么
- 任务范围集中在单个 resource 或一小组 resources

对于 compliance remediation agent，这覆盖了 80% 以上的任务。系统会预先获取 finding、受影响 resource、graph 中的 related resources、IaC location，以及相关 policies，然后在 agent 写第一行代码之前就全部注入。

**这是大多数基础设施 agents 应该开始的地方。** 如果 direct injection 就能解决问题，你就不需要 search 或 RAG。

### Level 2：Filtered Database Queries（中等数据量、结构化查询）

当 agent 需要探索超出预注入范围的数据时，比如浏览多个 resources、跨 accounts 对比，或者在运行时按它自己决定的维度筛选，那就给它提供由数据库支撑的 query tools。

这些就是上一节中的 typed API 模式：`queryResources`、`queryFindings`、`queryResourceGraph`。Agent 指定 filters（provider、resource type、region、severity、tags），系统返回预序列化后的结果。

这种方式适用于：
- Agent 需要在数百或数千个 resources 中搜索
- 查询是结构化的，通过已知维度过滤，而不是自由文本
- 数据已经在数据库中，并且带有索引字段

对于基础设施数据（Layers 1-4：resources、IaC、compliance、cost），filtered queries 几乎总是足够的。你搜索的是 resource type、region、severity、tag values，而不是语义相似度。对于这类查询，SQL `WHERE` 子句几乎总是比 vector search 更合适。

### Level 3：Full-Text Search（半结构化数据）

对于 organizational knowledge，比如 ADRs、runbooks、wiki pages、module docs、past incident reports，agent 无法靠结构化维度过滤，因为这些数据本身是文本。此时应使用基于关键词匹配的 full-text search。

```
Agent asks: "How did we handle VPC isolation for the payments team?"

Full-text search tool searches across:
  - ADRs in git repos
  - Wiki pages (Confluence, Notion)
  - Past agent session summaries
  - README files in infrastructure repos

Returns: Top 5 results ranked by relevance, with snippets.
```

PostgreSQL `tsvector` + `ts_rank`、Elasticsearch 或 Meilisearch 都可以。这里的查询是关键词驱动的（“VPC isolation payments”），而语料规模通常也足够小（几百到几千份文档），基本 full-text search 就能找到正确结果。

这种方式适用于：
- 语料规模较小到中等（< 50K 文档）
- 查询包含会出现在目标文档中的具体关键词
- 基础设施词汇足够精确，关键词匹配效果好（resource names、service names、team names）

### Level 4：RAG，Retrieval-Augmented Generation（大数据、语义查询）

RAG 增加了一层 vector search：文档先被切块、embedding 成向量、存入 vector database，再在查询时按语义相似度检索。检索出的 chunks 会和用户 prompt 一起注入 agent context。

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│  Embed   │────▶│  Vector  │────▶│  Top-K   │
│  Query   │     │  Query   │     │  Search  │     │  Results  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                        │
                                                        ▼
                                                   ┌──────────┐
                                                   │  Inject   │
                                                   │  into     │
                                                   │  Prompt   │
                                                   └──────────┘
```

在以下场景下使用 RAG：
- **大规模文档语料**，数千个 wiki pages、数百份 runbooks、多年的 incident reports
- **语义查询**，问题与答案使用的词汇不同，例如“我们组织对 public-facing storage 的 policy 是什么？”需要命中一篇讲 “S3 bucket ACLs” 的文档
- **跨域知识连接**，agent 需要把 ADR、past incident 和 naming convention 文档串起来

**以下场景不要用 RAG：**
- 你搜索的是结构化基础设施数据，应使用 filtered queries
- 你的语料很小（< 1K 文档），full-text search 更简单，而且通常更准确
- 查询里包含精确标识符（ARNs、resource names、finding IDs），关键词搜索更适合精确匹配

RAG 在基础设施数据上的常见陷阱：
- **错误地切分基础设施文档**，把 Terraform module doc 在 resource block 中间切开，只会产生垃圾 context
- **Embedding 基础设施术语效果不佳**，通用 embedding model 可能无法区分 “NSG”、“security group” 和 “firewall rule”
- **过度索引**，如果把每一份 cloud API response 都做 embedding，只会制造噪声。应只对包含 organizational knowledge 的文档做 embedding，而不是对原始 resource data 做 embedding

#### Vector Database 选项

| Option | 何时使用 |
|--------|---------|
| **pgvector**（PostgreSQL extension） | 如果你已经在用 PostgreSQL，就从这里开始。无需新基础设施。可处理数百万向量。 |
| **Pinecone / Weaviate / Qdrant** | 当你需要高级特性（hybrid search、filtering、multi-tenancy）且规模更大时使用专用 vector DB |
| **In-memory**（FAISS、HNSWlib） | 适合原型验证、小规模语料（< 100K vectors）或希望零额外基础设施时使用 |

### Level 5：MCP Resources（可浏览数据）

MCP（Model Context Protocol）支持一种 `resources` 原语，agent 可以浏览可用数据源列表，并按需读取其中某些资源。这适合暴露那些 agent 可能会用到、也可能用不到的结构化数据。

```
MCP server exposes:
  resource://cloud/aws/us-east-1/s3-buckets       → list of all S3 buckets
  resource://compliance/findings/high              → all HIGH severity findings
  resource://docs/adrs/vpc-isolation               → specific ADR document
  resource://policies/encryption                   → encryption policy

Agent browses the resource list, reads what it needs.
```

这种方式通常是对其他层级的补充。MCP resources 让 agent 可以自助获取它可能需要的数据，而不必把所有东西预注入。

### 如何选择合适的层级

```
"Fix this specific S3 encryption finding"
  → Level 1: Direct injection. You know exactly what context is needed.

"Show me all unencrypted S3 buckets across our AWS accounts"
  → Level 2: Filtered query. Structured search by resource type + property.

"How did we handle encryption for the payments team last quarter?"
  → Level 3: Full-text search. Keyword search across ADRs and past sessions.

"What are the best practices for encrypting data at rest in our org?"
  → Level 4: RAG. Semantic search across docs, policies, and past decisions.

"I need to understand this infrastructure before making changes"
  → Level 5: MCP resources. Agent browses available data and pulls what it needs.
```

在实践中，大多数基础设施 agents 会组合使用 Levels 1 + 2：先预注入已知 context，再给 agent 提供 query tools 获取剩余信息。当 agent 开始需要 organizational knowledge 时，再增加 Level 3。只有当 full-text search 在大规模场景下无法命中语义相关文档时，才增加 Level 4。

---

## Tools 与替代方案

### Asset Inventory（Layer 1：存在什么？）

这些工具负责收集与规范化 cloud resources：

| Tool | 它做什么 | Approach |
|------|---------|----------|
| **Your own scanners** | 使用 cloud provider SDKs 自定义扫描器 | 对扫描内容和存储方式拥有最大控制权 |
| [CloudQuery](https://github.com/cloudquery/cloudquery) | 将 cloud resources 同步到 PostgreSQL 或任意数据库，100+ plugins | 如果你不想自己构建 scanners，这是通用场景下最好的选项 |
| [Steampipe](https://github.com/turbot/steampipe) | 对 cloud APIs 提供 SQL 接口，可用 SQL 查询 AWS/Azure/GCP | 实时查询，不持久化（query → API call） |
| [Cartography](https://github.com/lyft/cartography) | 构建 asset 和 relationship 的 Neo4j graph（Lyft 开源） | Graph-native，包含 IAM relationship mapping |

**Cloud provider inventories**，比如 AWS Config + Resource Explorer、Azure Resource Graph、GCP Cloud Asset Inventory、OCI Search，适合作为实时查询的补充，但它们都是按 provider 分裂的，没有 cross-cloud 视图，也没有自定义 enrichment（IaC correlation、cost data、compliance linking）。

### Security & Compliance（Layer 3：哪里有问题？）

这些工具会产出进入 data plane 的 findings，但它们本身并不构建 data plane：

| Tool | 它做什么 |
|------|---------|
| [Prowler](https://github.com/prowler-cloud/prowler) | AWS、Azure、GCP 的 cloud security assessment，覆盖 CIS、SOC2、HIPAA benchmarks |
| [Checkov](https://github.com/bridgecrewio/checkov) | 针对 IaC 的静态分析（Terraform、CloudFormation、Kubernetes） |
| [Trivy](https://github.com/aquasecurity/trivy) | 针对 containers、IaC 和 cloud 的漏洞扫描器 |
| Cloud-native tools | AWS Security Hub、Azure Defender、GCP Security Command Center |

这些工具负责产生 compliance findings。你的 data plane 则负责存储这些 findings，把它们关联到受影响的 cloud resources，并通过 skill APIs 暴露给 agents。

### Storage（把数据放在哪里）

| Option | 何时使用 |
|--------|---------|
| **PostgreSQL**（带 JSON columns） | 从这里开始。一个数据库装下 resources、relationships（edge table）、findings、IaC state。Recursive CTEs 足以处理 2-3 跳 graph queries。 |
| **Neo4j / Neptune** | 只有在你需要复杂 multi-hop traversals，而 CTEs 已经不够高效时才使用。这会增加基础设施和同步复杂度。 |
| **pgvector** / vector database | 只有当 agents 无法通过关键词搜索找到相关文档时才考虑。大多数基础设施查询都能通过已知维度过滤，vector search 对 resource lookups 来说通常是过度设计。 |

---

## Data Freshness

陈旧数据比没有数据更糟。一个基于已删除 resource 行动的 agent，只会浪费时间并制造混乱。

| Data Type | 所需新鲜度 | 策略 |
|-----------|-----------|------|
| Cloud resources | 小时级 | 每 1-6 小时进行计划扫描 |
| Resource properties | 小时级 | 完整扫描或事件驱动（CloudTrail、Activity Log） |
| Relationships | 小时级 | 在 resource scan 过程中提取 |
| IaC state | 分钟级 | 在 git push 时解析（webhook 触发） |
| Compliance findings | 小时级 | 计划扫描（夜间或按需） |
| Cost data | 天级 | 每日从 billing APIs 同步 |
| Documentation | 天级 | 定时同步或变更 webhook |

对大多数基础设施 agents 来说，**每小时 cloud scan + 针对 IaC 的 git webhook triggers** 已经足够新鲜。只有那些需要在几分钟内采取行动的 incident response agents，才值得承担事件驱动更新（CloudTrail → update database）带来的额外复杂度。

---

## 下一章

[第 7 章：Change Control & GitOps →](./07-change-control-zh.md)

---

*由 [Cloudgeni](https://cloudgeni.ai) 团队打造，帮助你安全地用 Agents 扩展基础设施团队能力。*
