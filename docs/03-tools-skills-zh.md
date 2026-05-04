# 第 3 章：Tools、CLIs 与 Skills

> agent 如何获得能力，从 CLI tools 到结构化的 skill systems。

---

## Tool Landscape

基础设施 agents 需要访问真实工具：`terraform`、`aws`、`az`、`gcloud`、`kubectl`、`helm`、`git`、`checkov`、`tflint`，以及更多其他工具。问题不是 agent 是否需要 tools，而是如何以安全方式提供这些访问能力。

这是一条从 raw shell access（能力最强，安全性最低）到 structured skill systems（能力受限，安全性最高）的光谱。大多数生产系统会组合使用它们。

---

## CLI Tools：基础层

每个基础设施 agent 最终都需要运行 CLI commands。IaC 生态是围绕 CLI 构建的，没有什么 Terraform API 能完全替代 `terraform plan`，也没有什么 Azure SDK 能替代 `az` 所完成的一切。agent 的 sandbox image 就是它的 tool inventory。

### 核心 CLI Tooling

| Category | Tools | Purpose |
|----------|-------|---------|
| **IaC** | `terraform`, `tofu`, `pulumi`, `bicep` | 编写、plan、validate 基础设施代码 |
| **Cloud CLIs** | `aws`, `az`, `gcloud`, `oci` | 查询资源、管理配置 |
| **Kubernetes** | `kubectl`, `helm`, `kustomize` | cluster 操作、部署 |
| **Git** | `git`, `gh`, `glab` | 版本控制、创建 PR |
| **Security** | `checkov`, `tflint`, `trivy`, `prowler` | static analysis、compliance scanning |
| **Utilities** | `jq`, `yq`, `curl`, `envsubst` | 数据解析、HTTP 调用、templating |

### 让 CLI Access 更安全

给予 agent 无限制的 `bash` 是最简单的方法，也是最危险的方法。以下是收紧方式：

**1. Allowlisted commands**：只允许特定 binaries。agent 可以运行 `terraform plan`，但不能运行任意 `curl` 或 `bash -c`。

**2. 通过 environment 注入 credentials**：CLI 从 environment variables 读取 credentials。在运行时注入短期 tokens，而不是把任何 credential 烘焙到 image 中：

```
AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY + AWS_SESSION_TOKEN  (STS)
AZURE_CLIENT_ID + AZURE_CLIENT_SECRET + AZURE_TENANT_ID       (Service Principal)
GOOGLE_APPLICATION_CREDENTIALS                                  (Service Account)
GITHUB_TOKEN                                                    (Installation token)
```

完整的 credential broker pattern 参见[第 5 章：Credential Management](./05-credential-management-zh.md)。

**3. Version pinning**：在 sandbox Dockerfile 中将每个工具固定到特定版本。Terraform 从 1.8 升级到 1.9 可能改变 plan output format、破坏 provider 行为，或引入新的行为。

**4. Machine-readable output**：CLI output 往往很混乱，包含 progress bars、colour codes、pagination，以及与数据混杂的 warnings。应始终优先使用 structured output：

```bash
terraform plan -json              # Structured JSON instead of human-readable
terraform show -json              # JSON state output
aws ... --output json             # JSON instead of table format
az ... --output json              # JSON instead of table format
kubectl get ... -o json           # JSON output
checkov -o json                   # JSON findings
```

当没有 JSON output 可用时，model 就必须解析文本，这种方式虽然可行，但对 tool version 的变化较为脆弱。

**5. Typed CLI wrappers**：对于高风险或高频命令，把 CLI 包装成 typed function，以便验证 inputs 并解析 outputs：

```typescript
interface PlanResult {
  success: boolean;
  resources: { address: string; action: 'create' | 'update' | 'delete' | 'no-op' }[];
  error?: string;
}

async function terraformPlan(workDir: string): Promise<PlanResult> {
  const { stdout, exitCode } = await exec(
    'terraform plan -json -no-color',
    { cwd: workDir }
  );
  return parsePlanJson(stdout);
}
```

这是 raw CLI 与 structured capabilities 之间的桥梁。agent 调用的是 typed function，但底层实际运行的是 `terraform plan`。

### CLI 与 Structured Tools：何时使用哪一种

| Use CLI Directly | Use Typed Wrappers / Skills |
|------------------|---------------------------|
| 一次性查询（`aws s3 ls`） | 核心 agent loop 操作（plan、validate、PR） |
| 工具有良好的 `-json` output | output 需要 parsing 或 error classification |
| 低风险只读命令 | 高风险写操作 |
| 探索性 / debugging 任务 | 必须可靠执行的重复操作 |

---

## Structured Capability Systems

除了 CLI 之外，还有几种方式可以给 agent 提供更高层、更安全的 capabilities。一个好的系统应当提供：

- **Documentation**：agent 知道 capability 做什么、何时使用它，以及适用哪些 constraints
- **Typing**：inputs 和 outputs 有 schema，而不是任意字符串
- **Scoping**：不同 agents 拥有不同 capabilities。PR reviewer 不应拥有 `terraform apply`
- **Auditability**：每次 invocation 都要记录 inputs、outputs 和 context

### 1. Skills as Files（文档优先）

把 skills 写成 files，由 agent 读取并执行。这一模式因 Claude Code 的 `.claude/skills/` 约定而流行起来：

```
skills/
├── terraform-plan/
│   └── SKILL.md     # Instructions, constraints, examples
├── git-operations/
│   └── SKILL.md
└── cloud-credentials/
    └── SKILL.md
```

agent 通过读取 `SKILL.md` 来理解何时以及如何使用该 skill。指令中可以包含 constraints（“未经审批绝不能在 production 上运行”）、error handling（“如果 plan 超时，重试一次”）和 examples。

```markdown
# Terraform Plan Skill

## When to Use
After making changes to Terraform files, to validate your changes
produce the expected plan output.

## Constraints
- ALWAYS check the plan output before creating a PR
- If the plan shows unexpected changes, STOP and ask the user
- Maximum 10 plan iterations per session

## Error Handling
- If the pipeline fails, check the error output for syntax errors
- If authentication fails, request fresh credentials
```

**优点**：文档丰富；agent 可以推理何时使用 skill；易于 version control 和 review；skills 可以在运行时按 agent 注入。  
**缺点**：要求 agent 能正确解析并遵循指令（依赖 model）；结构化程度不如 typed function calls。

### 2. Subagents as Role-Scoped Capability Bundles

subagent 将一个 agent role 打包成可复用定义：prompt、model、tool scope、permission mode、max turns、skills、hooks 和 MCP access。在 Claude Code 中，它们可以存在于多个 scope：

| Scope | Typical Use |
|-------|-------------|
| **Managed / enterprise** | 组织级的 baseline roles 与 restrictions |
| **Project** (`.claude/agents/`) | 仓库特定的 reviewers、remediators 和 workflow helpers |
| **User** (`~/.claude/agents/`) | 可跨项目使用的个人 helpers |
| **Plugin / marketplace** | 与相关 skills 和 integrations 一起分发的打包 roles |

Managed subagents 对基础设施团队尤其重要，因为它们可以一次覆盖多层：

- **Role layer**：`security-reviewer`、`terraform-reviewer`、`drift-remediator`、`incident-triage`
- **Prompt layer**：角色特定的 instructions、review criteria 和 escalation rules
- **Runtime layer**：model 选择、effort level、max turns 和 delegation boundaries
- **Capability layer**：allowed tools、预加载的 skills 和带 scope 的 MCP servers
- **Governance layer**：enterprise-managed definitions 可以覆盖不安全的 project 或 user variants

这使 managed subagents 成为一种实用的企业控制手段，用于在不同仓库之间标准化 agent 行为。它们**不能**替代 sandboxing、credential brokering、approval gates、deterministic validation 或 action trails。应把它们视为高层的 role/capability policy，而底层仍需要额外 enforcement。

对于 multi-tenant products，即使你并不直接使用 Claude Code，同样的模式也适用：将解析后的 agent definitions 存储为带版本的 artifacts，像对待 policy 一样对它们进行 review，并让每次运行的实际 role configuration 可见。

### 3. MCP（Model Context Protocol）

这是 Anthropic 的开放标准，用于将 agents 连接到外部 tools 和 data sources。实际上，MCP 已从“typed tool bridge”扩展为更广义的 interoperability layer，用于连接**tools、resources、prompts 和 long-running task flows**。MCP servers 通常通过 stdio 或 HTTP transports 暴露：

```typescript
import { McpServer } from '@modelcontextprotocol/sdk/server';

const server = new McpServer({ name: 'infra-tools' });

server.tool('terraform_plan',
  { pipelineId: z.string() },
  async ({ pipelineId }) => {
    const result = await triggerPlan(pipelineId);
    return { content: [{ type: 'text', text: JSON.stringify(result) }] };
  }
);
```

现代 MCP 部署还可能包括：

- **Structured outputs**，因此 tool results 不必从 plain text 中解析
- **Elicitation / user-input flows**，供 agent 发问
- **Task-oriented operations**，适合 long-running work，而不是单次 request/response 调用
- **Registry metadata**，用于 discovery 和 installation
- **Authorization conventions**，让 clients 能一致地协商 OAuth 及相关 flows

**优点**：标准协议；typed schemas；多个 LLM providers 支持；vendor 和 community servers 生态增长很快。  
**缺点**：仍然需要 operational discipline，包括 version pinning、auth hardening、allowlists，以及跨 client 的 compatibility testing。

**Operational guidance**：

- 固定你测试过的 **server version** 和 **MCP spec version**
- 把 registry presence 当作**可发现性**，而不是信任
- 生产环境优先使用**内部 registry 或 allowlist**
- 在完成 review 之前，把 tool descriptions 和 annotations 视为不可信输入

### 4. A2A（Agent-to-Agent Protocols）

MCP 并不适合所有集成场景。当一个 agent 需要把工作委派给另一个拥有自身 memory、approvals、artifacts 和 lifecycle 的 autonomous application 时，应使用 **agent-to-agent protocol**，例如 **A2A**。

以下情况适合使用 **A2A**：

- 远程系统拥有自己的 credentials 和 policy enforcement
- 工作是 long-running 且 task-oriented 的
- 响应可能包含 artifacts、status changes、follow-up questions 或可 resume 的工作项

以下情况适合使用 **MCP**：

- 你是在向 model runtime 暴露 tools、resources 或 prompts
- 调用是狭窄、typed，且从属于调用方 agent 的

在实践中，许多 infra systems 会在 **worker 内部使用 MCP**，并在**产品边界之间使用 A2A**。

### 5. LangChain / LangGraph Tools

使用 decorators 的 Python-native tool registration：

```python
from langchain.tools import tool

@tool
def terraform_plan(pipeline_id: str) -> str:
    """Trigger a Terraform plan and return the result."""
    result = requests.post(f"{API_URL}/run-pipeline", json={"id": pipeline_id})
    return result.json()

agent = create_react_agent(llm, [terraform_plan, ...])
```

**优点**：简单的 Python-native API；生态大；适配任意 LLM。  
**缺点**：仅支持 Python；tool docs 基本仅限 docstrings；没有内建 isolation。

### 6. OpenAI 风格的 Function Calling

把 tools 定义为 JSON schemas，让 model 生成 structured arguments：

```typescript
const tools = [{
  type: 'function',
  function: {
    name: 'terraform_plan',
    description: 'Trigger a Terraform plan execution',
    parameters: {
      type: 'object',
      properties: {
        pipeline_id: { type: 'string', description: 'The pipeline to run' },
      },
      required: ['pipeline_id'],
    },
  },
}];
```

**优点**：model 生成经过验证的 JSON；schema 与 execution 清晰分离。  
**缺点**：文档能力仅限 schema（没有丰富指令）；绑定在支持 function calling 的 providers 上。

### 对比

| Approach | Documentation | Typing | Isolation | Ecosystem |
|----------|--------------|--------|-----------|-----------|
| **CLI tools** (direct) | Man pages / `--help` | None (strings) | Sandbox-level | Entire IaC ecosystem |
| **Typed CLI wrappers** | Code comments | Strong | Sandbox-level | Build your own |
| **Skills as files** | Rich (full markdown) | Via code | Per-file | Growing (Claude, community) |
| **Subagents / agent roles** | Role prompt + frontmatter/config | Via configured tools | Per-agent/session | Growing in Claude-style runtimes |
| **MCP** | Schema + description | Strong (Zod) | Per-server | Growing fast (vendor-backed) |
| **A2A** | Agent cards + task schema | Strong | App boundary | Emerging interoperability layer |
| **LangChain tools** | Docstrings | Python types | None (same process) | Largest |
| **Function calling** | Schema only | JSON Schema | Your responsibility | Universal |

### 组合方式：Subagents + Skills + MCP + A2A + CLIs

这些方式并不是互斥的，它们可以层层叠加：

- **CLIs** 是基础。agent 在 sandbox 中运行 `terraform`、`aws`、`git`。这是原始 capability layer。
- **Skills** 定义如何正确使用这些 CLIs。一个 skill 会说明“编写 Terraform 时遵循这些约定，使用 plan 校验，最多 10 次迭代”。这是 best-practices layer。
- **Subagents / managed agent roles** 打包“由谁来做这项工作”：role prompt、model、allowed tools、skills、MCP access 和 safety posture。它们可以同时覆盖 runtime、capability 和 policy layers 的一部分。
- **MCP** 连接到**实时数据和 APIs**。一个 MCP server 可以让 agent 访问 Terraform Registry、workspace state 或 cloud resource inventory。这是 data layer。
- **A2A** 连接到**其他 autonomous systems**。远程 remediation agent、ticketing copilot 或 approval service 可以保有自己的 state，同时参与更广泛的 workflow。

HashiCorp 的 Claude plugin 直接展示了其中三层：安装在环境中的 CLI tools、用于 Terraform code generation patterns 的 skills，以及用于访问实时 Terraform Registry 和 Cloud API 的 MCP server。

---

## Tool Allow/Deny Lists

限制每种 agent 类型可访问的 tools：

```typescript
// Example agent configurations
const AGENT_CONFIGS = {
  'pr-reviewer': {
    allowedTools: ['git-diff', 'pr-comment', 'iac-lint'],
    maxTurns: 20,
    producesCodeChanges: false,
  },
  'compliance-remediation': {
    allowedTools: [],  // All tools (needs to write code, run plans, create PRs)
    maxTurns: 50,
    producesCodeChanges: true,
  },
  'drift-detection': {
    allowedTools: ['terraform-plan', 'drift-verification', 'notify-slack'],
    maxTurns: 10,
    producesCodeChanges: false,
  },
};
```

关键原则是：**先默认收紧，再按需放开。** drift detection agent 不需要 git push。PR reviewer 不需要 cloud credentials。

---

## 现实世界中的 IaC Skills 生态

vendors、cloud providers 和 community 都已经发布了生产级 skills 和 MCP servers。你可以直接采用它们、把它们当模板，或仅仅研究其中模式。

### Agent Skills Format

标准格式由 [Anthropic skills spec](https://github.com/anthropics/skills)（72K+ stars）推动普及，在结构上非常简单：一个目录，包含必需的 `SKILL.md` 文件，里面有 YAML frontmatter（name、description）以及可选的 scripts 和 assets。frontmatter 遵循一个**三级 progressive disclosure** 模型：

```yaml
---
# Level 1: Frontmatter (always loaded into agent context for discovery)
name: terraform-style-guide
description: Write and review Terraform following HashiCorp style conventions
---

# Level 2: SKILL.md body (loaded on demand when skill is activated)
## When to Use
Use when writing new Terraform configurations or reviewing existing HCL...

## Instructions
Follow these conventions...

## References
- [reference: ./hashicorp-style-guide.md]  # Level 3: linked files (loaded when needed)
```

只有在 skill 被激活时，agent 才会加载完整 instructions；name 和 description 则始终保留在 context 中用于 discovery。

对于 multi-tenant products，应按**层级**解析 skills 和 role definitions：

1. vendor-curated 或 platform-curated base skills
2. organization-level overrides 和 custom skills
3. repository-local skills，用于团队特定 workflows

应对解析后的 skill 和 subagent set 进行版本化、缓存，并让 logs 和 UI 可以查看当前激活的 manifest。这一点与单个文件内容本身同样重要。

### Vendor-Official Skills

#### HashiCorp - [hashicorp/agent-skills](https://github.com/hashicorp/agent-skills)

这是面向 Terraform 最完整的 vendor skill set，组织为三个 plugin bundle：

| Plugin | Skills Included | Focus |
|--------|----------------|-------|
| `terraform-code-generation` | `terraform-style-guide`, `terraform-test`, `azure-verified-modules` | 编写正确的 HCL、testing |
| `terraform-module-generation` | `refactor-module`, `terraform-stacks` | module 抽取、HCP Terraform Stacks |
| `terraform-provider-development` | `new-terraform-provider`, `provider-actions`, `provider-resources` | 构建 Terraform providers |

`refactor-module` skill 值得特别注意，因为它涵盖了 **state migration patterns**（`moved` blocks、`terraform state mv`），如果执行错误，blast radius 很高。`terraform-stacks` skill 则明确推荐 **workload identity (OIDC)** 和 ephemeral tokens。

#### Pulumi - [pulumi/agent-skills](https://github.com/pulumi/agent-skills)

同时覆盖 authoring 和 migration workflows：

| Category | Skills | Focus |
|----------|--------|-------|
| **Authoring** | `pulumi-best-practices`, `pulumi-component`, `pulumi-automation-api`, `pulumi-esc` | 编写 Pulumi programs、ESC secrets management |
| **Migration** | `pulumi-terraform-to-pulumi`, `cloudformation-to-pulumi`, `pulumi-cdk-to-pulumi`, `pulumi-arm-to-pulumi` | 完整 migration workflows，含 state translation |

migration skills 强调 **“zero-diff preview” requirement**，即导入 state 之后，Pulumi preview 必须显示无变更，才能认为迁移成功。这是任何 state migration skill 都应具备的关键安全模式。

### Vendor MCP Servers

#### HashiCorp - [hashicorp/terraform-mcp-server](https://github.com/hashicorp/terraform-mcp-server)

通过 MCP 提供对 Terraform 生态的实时访问：
- **Terraform Registry**：查询 providers、modules、policies
- **Terraform Cloud/Enterprise**：workspace CRUD、run management、private registry
- 同时支持 `stdio` 和 `StreamableHTTP` transports

> **安全说明**：该仓库明确警告要限制 `MCP_ALLOWED_ORIGINS`，以缓解 cross-origin/DNS rebinding attacks，并推荐只在本地、配合可信 clients 使用。

#### AWS - [awslabs/mcp](https://github.com/awslabs/mcp)

AWS 的 MCP monorepo（8K+ stars）中包含三个与 IaC 相关的 servers：

| Server | Capabilities | Risk Level |
|--------|-------------|------------|
| **aws-iac-mcp-server** | CloudFormation/CDK docs 搜索、template validation、compliance checks、deployment troubleshooting | Low（只读、提供 guidance） |
| **cfn-mcp-server** | 通过 Cloud Control API 直接 CRUD 1100+ AWS resource types、IaC Generator | **Very High**（可以创建/删除资源） |
| **terraform-mcp-server** | AWS Terraform best practices、Checkov scanning、执行 `terraform plan/apply/destroy` | **Very High**（可以运行 apply/destroy） |

> **关键区别**：`aws-iac-mcp-server` 只提供 guidance，相对安全。`cfn-mcp-server` 和 `terraform-mcp-server` 可以造成破坏性更改，应视为 Tier 3/4 tools，需要显式 approval gates。

#### Pulumi MCP Server

可通过 npm 包 `@pulumi/mcp-server` 或 `docker pull mcp/pulumi` 获取。它与 Pulumi Cloud 交互，支持 stack preview、deploy、读取 outputs 和 registry queries。需要 OAuth flow 以及带 org scope 的 Pulumi Access Token。

### Community Skills（值得关注）

| Repository | Stars | Focus | Why It's Notable |
|-----------|-------|-------|-----------------|
| [antonbabenko/terraform-skill](https://github.com/antonbabenko/terraform-skill) | 1.1K+ | Terraform 与 OpenTofu | 由 Anton Babenko 编写，他是高产的 Terraform 社区贡献者。单文件 `SKILL.md` 内容全面，覆盖 testing、modules、CI/CD 和 production patterns |
| [akin-ozer/cc-devops-skills](https://github.com/akin-ozer/cc-devops-skills) | 70+ | 多工具 DevOps | 31 个 skills，覆盖 Terraform、Terragrunt、Ansible、Kubernetes、Helm、GitHub Actions、GitLab CI、Jenkins、PromQL 等 |
| [terramate-io/agent-skills](https://github.com/terramate-io/agent-skills) | 25+ | Terraform、OpenTofu、Terramate | state splitting、drift reconciliation、stack management |
| [dirien/claude-skills](https://github.com/dirien/claude-skills) | — | Pulumi（TS/Go/Python） | Pulumi 社区 skills，强调 ESC + OIDC patterns |
| [sigridjineth/hello-ansible-skills](https://github.com/sigridjineth/hello-ansible-skills) | 23+ | Ansible | Playbook 开发、debugging、shell-to-ansible 转换 |

### Curated Skill Directories

如果要发现更多 skills：

| Directory | Stars | Description |
|----------|-------|-------------|
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | 7.5K+ | 300+ agent skills 目录，跨多个平台 |
| [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills) | 7.3K+ | 精选 Claude skills 列表 |

---

## IaC Skill Risk Matrix

并非所有 skills 风险都相同。应把每一种映射到正确的控制措施：

```
                    READ-ONLY                              WRITE / EXECUTE
              ┌──────────────────────────────┬──────────────────────────────────┐
              │                              │                                  │
  GUIDANCE    │  LOW RISK                    │  MEDIUM RISK                     │
  (no tool    │  terraform-style-guide       │  refactor-module (state mv)      │
   calls)     │  pulumi-best-practices       │  terraform-stacks (deploy)       │
              │  aws-iac-mcp-server          │  migration skills (state import) │
              │                              │                                  │
              │  Controls: code review only  │  Controls: + validation gates    │
              ├──────────────────────────────┼──────────────────────────────────┤
              │                              │                                  │
  EXECUTION   │  MEDIUM RISK                 │  VERY HIGH RISK                  │
  (tool       │  terraform-mcp (registry)    │  cfn-mcp-server (CRUD 1100+)    │
   calls)     │  pulumi-mcp (query stacks)   │  terraform-mcp (apply/destroy)  │
              │  checkov scanning            │  aws terraform-mcp (apply)       │
              │                              │                                  │
              │  Controls: + credential      │  Controls: + sandbox + approval  │
              │  scoping + audit             │  gates + separate prod creds     │
              └──────────────────────────────┴──────────────────────────────────┘
```

---

## Skill Supply Chain Security

skills 不是“只是文档”。它们是**可执行流程**，会诱导 tool calls、shell commands 和 credential exposure。行业已经在这方面付出过代价：

- **恶意 skill marketplaces**：大量上传伪装成有用 skills 的 stealer malware
- **“Markdown is an installer”**：某个 skill 的 setup instructions 导向恶意基础设施和分阶段 payload chain
- **通过 skills 的 prompt injection**：嵌入在 `SKILL.md` 中的指令可操纵 agent 行为
- **远程内容抓取**：在运行时用 `curl` 获取外部 URL 的 skills，是间接 injection vector

### IaC Skills 的 Vetting Checklist

```
BEFORE INSTALLING ANY SKILL:

[ ] Source is vendor-official or from a known, trusted publisher
[ ] Registry entry or marketplace presence is treated as discovery, not trust
[ ] Reviewed SKILL.md for suspicious instructions (fetch URLs, run scripts, disable security)
[ ] No embedded scripts that execute on install or setup
[ ] No references to external URLs that fetch content at runtime
[ ] Pinned to a specific version/commit hash (never "latest")
[ ] Pinned MCP server image/package/version if the skill depends on MCP
[ ] If from a marketplace: check scanning results, publisher history, star count
[ ] If it touches credentials: verify it recommends OIDC/short-lived tokens, not static keys
[ ] If it can run apply/destroy: ensure it's behind approval gates in your system

ONGOING:

[ ] Re-scan periodically (skills can be updated maliciously)
[ ] Monitor for CVEs in skill dependencies
[ ] Maintain an internal allowlist of approved skills
[ ] Mirror critical skills and MCP servers into an internal registry when possible
[ ] Block unknown publishers by default
```

### 安全默认姿态：Read-Only + PR-First

对于 IaC skills，安全的采用姿态应当是：

1. **在开发环境**：skills 可以生成代码并提出 diffs
2. **在 CI 中**：skills 可以运行 `plan`/`preview`/`validate` 并生成报告
3. **在生产环境**：skills 打开 PR，它们绝不直接 `apply`
4. **对于 apply/destroy**：要求显式的 “break-glass” approval，并使用单独的 credentials

这与 vendor skills 的设计方式一致：HashiCorp 的 skills 提供 guidance 并鼓励进行 plan verification；Pulumi 的 migration skills 要求在认为成功之前达到 “zero-diff preview”。

---

## 下一章

[第 4 章：Sandboxed Execution →](./04-sandboxed-execution-zh.md)
