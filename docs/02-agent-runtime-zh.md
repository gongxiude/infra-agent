# 第 2 章：Agent Runtime 与 Orchestration

> 如何选择 LLM runtime、task queueing、worker isolation、consumer groups 和 recovery。

---

## 核心问题

基础设施 agent 并不是一个简单的 request-response API 调用。它是一个**长时间运行、有状态、多步骤的过程**，并且：

- 可能运行几分钟到几小时（等待 CI pipeline、人工审批）
- 会使用昂贵的 LLM tokens 和 cloud API 调用
- 必须能在 worker 崩溃和重启后继续存活
- 可能需要 pause 和 resume（human-in-the-loop）
- 绝不能干扰其他并发 agent

本章涵盖两层：**agent runtime**（在 worker 内驱动 LLM loop 的部分）和 **orchestration layer**（任务如何被 dispatch、queue 和 recover）。

---

## 选择 Agent Runtime

agent runtime 是驱动一切的内部 loop：

```
prompt → LLM → tool_use → execute tool → result → LLM → tool_use → ... → final answer
```

这个 loop 需要处理 tool registration、token counting、error recovery、multi-turn context 和 stopping conditions。你可以自己实现，也可以使用替你管理这些内容的 framework。

### 选项 1：Anthropic Claude Agent SDK

[Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk-typescript)（`@anthropic-ai/claude-agent-sdk`）是 Anthropic 官方的 Claude agent runtime。它也是 Claude Code 所使用的同一套引擎。提供 TypeScript 和 Python 版本。

这个 SDK 管理完整的 agentic loop：Claude 进行推理、调用工具、读取结果，并持续执行直到任务完成。你可以控制可用工具、设置 budget 限制，并实时 stream events。

```typescript
import { query, tool, createSdkMcpServer } from "@anthropic-ai/claude-agent-sdk";
import { z } from "zod";

// Define a custom tool
const runTerraformPlan = tool(
  "terraform_plan",
  "Run terraform plan in the given directory",
  { workDir: z.string().describe("Working directory path") },
  async ({ workDir }) => {
    const result = await exec("terraform plan -json -no-color", { cwd: workDir });
    return { content: [{ type: "text", text: result.stdout }] };
  }
);

// Create an in-process MCP server for custom tools
const infraTools = createSdkMcpServer({
  name: "infra-tools",
  tools: [runTerraformPlan],
});

// Run the agent — the SDK handles the full loop
for await (const message of query({
  prompt: "Fix the unencrypted S3 bucket in modules/storage/main.tf",
  options: {
    systemPrompt: hardRules + policyDigest,
    allowedTools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
    mcpServers: { "infra-tools": infraTools },
    maxTurns: 50,
    permissionMode: "bypassPermissions",
    cwd: "/workspace/infra-repo",
  },
})) {
  if (message.type === "result" && message.subtype === "success") {
    console.log("Agent completed:", message.result);
  }
}
```

**关键特性**：内建 file 和 shell tools、MCP server support、subagent delegation（`Task` tool）、用于复用角色的 managed/project subagent definitions、通过 `session_id` resume session、cost budgets（`maxBudgetUsd`），以及用于 tool-use 前后验证的 lifecycle hooks。

### 选项 2：OpenAI Codex CLI / Agents SDK

OpenAI 现在提供两层互补的 agent 构建方式：

**Codex CLI**（[github.com/openai/codex](https://github.com/openai/codex)）是一个开源 terminal agent（Rust，Apache-2.0），可以在本地读取、修改并执行代码。它底层使用 Responses API，并带有平台相关的 sandboxing（macOS 上是 Seatbelt，Linux 上是 Landlock）。当 agent 运行在工作站或临时 repo checkout 中时，它尤其适合。

**Agents SDK**（[OpenAI docs](https://platform.openai.com/docs/guides/agents-sdk)）是 OpenAI 用于构建自定义 agents 的应用 framework，支持 **TypeScript 和 Python**。它支持 typed tools、hosted tools、MCP servers、handoffs、session state、tracing 和 guardrail hooks。对于长时间运行的任务，底层的 Responses API 也支持 server-managed conversation state、background execution 和 webhook 风格的 completion flows。

```typescript
import { Agent, run, tool } from "@openai/agents";
import { z } from "zod";

const terraformPlan = tool({
  name: "terraform_plan",
  description: "Run terraform plan and return the JSON output",
  parameters: z.object({ workDir: z.string() }),
  execute: async ({ workDir }) => {
    const result = await exec("terraform plan -json -no-color", { cwd: workDir });
    return result.stdout;
  },
});

const agent = new Agent({
  name: "Remediation Agent",
  instructions: "Fix compliance findings by editing Terraform files.",
  tools: [terraformPlan],
});

const result = await run(agent, "Fix the unencrypted S3 bucket", {
  conversationId: existingConversationId,
});

console.log(result.finalOutput);
```

**Raw Responses API**：如果你需要最大控制力，可以直接调用 `client.responses.create()`。`previous_response_id` 参数可以在不重新发送完整 conversation history 的情况下，在多轮之间保持 reasoning state。只有当你需要自定义 background-mode orchestration、自己的 checkpointing model，或者对 tool routing 与 retries 进行非常明确的控制时，才应选择这条路径。

### 选项 3：LangChain / LangGraph

这是 Python 生态中最流行的 agent frameworks。[LangChain](https://github.com/langchain-ai/langchain) 提供简单的 ReAct agent loop。[LangGraph](https://github.com/langchain-ai/langgraph) 则加入带状态的 graph 和 conditional routing，适合像“scan → triage → remediate → validate → PR”这样复杂的 multi-step workflow。

```python
from langchain_anthropic import ChatAnthropic
from langchain.tools import tool
from langgraph.prebuilt import create_react_agent

@tool
def terraform_plan(work_dir: str) -> str:
    """Run terraform plan and return the result."""
    result = subprocess.run(
        ["terraform", "plan", "-json"],
        cwd=work_dir, capture_output=True, text=True,
    )
    return result.stdout

llm = ChatAnthropic(model="claude-sonnet-4-20250514")
agent = create_react_agent(llm, [terraform_plan])

result = agent.invoke({
    "messages": [{"role": "user", "content": "Fix the S3 encryption finding"}]
})
```

**优点**：适配任意 LLM provider（把 `ChatAnthropic` 替换为 `ChatOpenAI` 即可）、拥有大型预构建工具生态、LangGraph 原生支持 checkpointing 和 human-in-the-loop。  
**缺点**：抽象层较重、仅支持 Python，并且通过 chain 调试时可能不够透明。

### 选项 4：Direct API Wrapper（自行构建）

使用原始的 Anthropic 或 OpenAI API，并自己编写 loop。控制力最大，抽象最少。当你需要自定义 retry logic、token budgeting、非标准 tool execution，或希望避免 framework dependencies 时，选择这一方式。

```typescript
import Anthropic from "@anthropic-ai/sdk";

const client = new Anthropic();

async function runAgentLoop(
  prompt: string,
  tools: Anthropic.Tool[],
  executeToolCall: (name: string, input: unknown) => Promise<string>,
  maxTurns: number = 50,
): Promise<string> {
  const messages: Anthropic.MessageParam[] = [{ role: "user", content: prompt }];

  for (let turn = 0; turn < maxTurns; turn++) {
    const response = await client.messages.create({
      model: "claude-sonnet-4-20250514",
      max_tokens: 8192,
      tools,
      messages,
    });

    // Collect text and tool use blocks
    messages.push({ role: "assistant", content: response.content });

    if (response.stop_reason === "end_turn") {
      // Agent is done — extract final text
      const text = response.content.find(b => b.type === "text");
      return text?.text ?? "";
    }

    // Execute tool calls and feed results back
    const toolResults = [];
    for (const block of response.content) {
      if (block.type === "tool_use") {
        const result = await executeToolCall(block.name, block.input);
        toolResults.push({
          type: "tool_result" as const,
          tool_use_id: block.id,
          content: result,
        });
      }
    }
    messages.push({ role: "user", content: toolResults });
  }

  throw new Error("Agent exceeded max turns");
}
```

核心 loop 大约只有 30 行。你可以在其上继续加入 tool definitions、error handling、token tracking 和 streaming。

### 选项 5：Open-Source Agent Frameworks

除了 vendor SDK 之外，越来越多的 open-source frameworks 也能替你处理 agentic loop，而且大多数都与具体 LLM provider 无关，因此你可以在不重写 agent 的情况下切换 model。

#### Python Frameworks

| Framework | Stars | Key Differentiator | Best For |
|-----------|-------|-------------------|----------|
| [**CrewAI**](https://github.com/crewAIInc/crewAI) | ~57K | 基于角色的 multi-agent crews，带确定性的 Flows orchestration | 多 agent 协作（scan agent → triage agent → remediation agent） |
| [**Pydantic AI**](https://github.com/pydantic/pydantic-ai) | ~15K | type-safe、经 Pydantic 验证的 structured outputs。“FastAPI for agents” | 对已验证 typed outputs 要求高的基础设施 agents |
| [**Smolagents**](https://github.com/huggingface/smolagents) (HF) | ~26K | agent 写可执行 Python code，而不是 JSON tool calls。核心约 ~1K LOC | 轻量级 agents、code-generation-first workflows |
| [**Haystack**](https://github.com/deepset-ai/haystack) (deepset) | ~22K | pipeline-as-graph 架构，可序列化为 YAML，适合 K8s | RAG + agent pipelines、生产级 search/retrieval workflows |
| [**Google ADK**](https://github.com/google/adk-python) | ~16K | Google 背书，针对 Gemini 优化，但 model-agnostic | GCP-native 团队、多语言（Python/Go/TS） |
| [**Strands Agents**](https://github.com/strands-agents/sdk-python) (AWS) | ~10K | AWS 背书、model-driven 方法、1400 万+下载量 | AWS-native 团队、Bedrock 集成 |

**关于 AutoGen 的说明**：Microsoft 的 [AutoGen](https://github.com/microsoft/autogen)（约 55K stars）开创了 multi-agent conversations，但现在已进入**maintenance mode**。新的开发工作已转移到 Microsoft Agent Framework（Semantic Kernel）。社区 fork [AG2](https://github.com/ag2ai/ag2) 仍在积极开发。

#### TypeScript Frameworks

| Framework | Stars | Key Differentiator | Best For |
|-----------|-------|-------------------|----------|
| [**Mastra**](https://github.com/mastra-ai/mastra) | ~20K | 全栈 TS agent framework，内建 RAG、memory、MCP、evals，支持 81+ providers | 完整的 TypeScript agent 平台 |
| [**Vercel AI SDK**](https://github.com/vercel/ai) | ~22K | streaming-first，原生适配 React/Next.js。每月 2000 万+ npm downloads | 面向 Web 的 agents、streaming UI、Next.js 应用 |

#### 它们如何处理 Agentic Loop

这些 framework 都实现了同样的核心模式，即 LLM → tool call → execute → result → LLM，但实现风格不同：

- **CrewAI** 在 loop 之上再加一层：你定义 agent 的 *roles* 和 *goals*，然后 framework 使用确定性的 Flows 来编排多 agent 协作和步骤顺序。
- **Pydantic AI** 强调 type safety：每个 tool input 和 agent output 都经过 Pydantic 验证。`@agent.tool` decorator 让工具可以访问 agent context（dependencies、retries）。
- **Smolagents** 完全采用另一种方法：agent 不生成 JSON tool calls，而是写可执行的 Python code。这意味着它能更自然地组合工具、使用 loops 和 conditionals，对于涉及 scripting 的基础设施任务尤其值得关注。
- **Mastra** 为 2,400+ models 提供统一的 `"provider/model-name"` 字符串接口，并内建 MCP server support、memory management 和 workflow orchestration。
- **Vercel AI SDK** 使用 `generateText`/`streamText` 并设置 step limit。它会把 tool calls 和中间结果实时 stream 到 UI，这对于 user-facing agent interfaces 是独特能力。

### 对比

| | Language | LLM Lock-in | Tool System | Session Mgmt | Multi-Agent | Complexity |
|---|---|---|---|---|---|---|
| **Claude Agent SDK** | TS, Python | Claude | MCP + built-in tools | Resume by ID | Subagents | Low |
| **OpenAI Agents SDK** | TS, Python | OpenAI | Function tools + hosted tools + MCP | Sessions / `conversationId` / `previous_response_id` | Handoffs | Low |
| **LangChain/LangGraph** | Python | Any | Decorators + schemas | Checkpoints | Subgraphs | Medium-High |
| **CrewAI** | Python | Any | Decorators + custom | Flows state | Role-based crews | Medium |
| **Pydantic AI** | Python | Any | Typed decorators | You build | You build | Low-Medium |
| **Smolagents** | Python | Any | Code-as-action | You build | Multi-agent | Low |
| **Mastra** | TypeScript | Any (81+ providers) | MCP + custom | Built-in memory | Workflows | Medium |
| **Vercel AI SDK** | TypeScript | Any | JSON schema | You build | You build | Low-Medium |
| **Direct API** | Any | Any | JSON schema | You build | You build | High (but simple) |

### 你应该选择哪一个？

- **先从单个 agent 开始**，除非你能证明确实需要更多。只有当单个 prompt/tool inventory 变得过宽、难以稳定评估，或大到无法舒适地放进 context 中时，再加入 handoffs、subagents 或 manager-worker patterns。
- 如果你基于 Claude 构建，并希望以最快路径得到一个带内建 file/shell tools、MCP support 和 session management 的可用 agent，就选 **Claude Agent SDK**。
- 如果你基于 GPT models 构建，并希望使用一个当前的官方 framework，且它在 TypeScript 或 Python 中都支持 tracing、sessions、hosted tools、MCP support 和 handoffs，就选 **OpenAI Agents SDK**。
- 如果你需要 provider flexibility、拥有带 conditional routing 的复杂 multi-step workflows，或者需要最大的预构建 integrations 生态，就选 **LangChain/LangGraph**。
- 如果你的架构本身就是 multi-agent（例如 scanning agent hand off 给 remediation agent，后者再 hand off 给 review agent），并且你想要 role-based orchestration，就选 **CrewAI**。
- 如果你希望得到 type-safe、validated outputs，同时尽量减少 framework 开销，尤其适用于 structured data 很重要的基础设施 agents，就选 **Pydantic AI**。
- 如果你使用 TypeScript 构建，并且希望得到 provider-agnostic 且支持 MCP 的 framework，就选 **Mastra** 或 **Vercel AI SDK**。
- 如果你需要最大控制力、希望避免 framework dependencies，或者有非标准执行需求，就选 **Direct API wrapper**。

这些方案最终都产生同一种输出：一个 loop，驱动 LLM 通过 tool calls 持续执行直到任务完成。它们的差异在于抽象层级、生态，以及你能使用哪些 LLM providers。

---
