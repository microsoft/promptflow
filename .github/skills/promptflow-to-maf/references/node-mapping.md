# Node Mapping Reference

> Lookup table for converting Prompt Flow node types to MAF equivalents.
> Read this when you need to map a specific Prompt Flow concept to MAF code.

## Core Mapping Table

| Prompt Flow Concept | MAF Equivalent |
|---|---|
| `flow.dag.yaml` (flow definition) | `WorkflowBuilder(name=..., start_executor=...).add_edge(...).build()` |
| Any node | `Executor` subclass with a `@handler` method |
| LLM node (`type: llm`) | `Agent(client=OpenAIChatClient(...), instructions=...)` inside an Executor |
| Python node (`type: python`, `source.type: code`) | Plain Python logic inside an `Executor` `@handler` |
| Custom-tool node (`type: python`, `source.type: package`) | **Call the tool's underlying Python function directly inside an `Executor` `@handler`. Do NOT remap to `OpenAIChatClient` / `Agent`.** See [topics/custom-tool-nodes.md](../topics/custom-tool-nodes.md). |
| Prompt node (`.jinja2` template) | System prompt string passed to `Agent(instructions=...)`, or string formatting in `@handler` |
| Conditional / If node (`activate_config`) | `.add_edge(source, target, condition=fn)` |
| Parallel nodes (no shared deps) | `.add_fan_out_edges(source, [targetA, targetB])` |
| Merge / aggregate node | `.add_fan_in_edges([sourceA, sourceB], target)` |
| `aggregation: true` node (eval batch) | Standalone function + `EvalRunner` orchestrator. See [topics/evaluation-flows.md](../topics/evaluation-flows.md). |
| Embed Text + Vector Lookup + LLM (RAG) | `AzureAISearchContextProvider` via `context_providers=[...]` on `Agent` |
| Python tool node | Plain function passed to `Agent(tools=[fn1, fn2])` |
| Flow inputs | Type annotation on start Executor's `@handler` parameter (use `@dataclass` for multiple inputs) |
| Flow outputs (`is_chat_output`) | `await ctx.yield_output(value)` in the terminal Executor |
| Connections (credentials) | Environment variables + `OpenAIChatClient(azure_endpoint=..., api_key=...)` for key auth, or `credential=DefaultAzureCredential()` for Microsoft Entra / managed identity. |
| `chat_history` input | Format into prompt string in an InputExecutor before passing to Agent |
| Variants | Separate Agent instances with different `instructions` strings |
| Multimodal input (image URL) | `Content.from_uri(url, media_type="image/png")` inside a `Message` (see [topics/multimodal.md](../topics/multimodal.md)) |
| Multimodal input (base64 image) | `Content.from_data(data=bytes, media_type="image/png")` inside a `Message` |
| `custom_llm` node with images | Executor that builds a `Message("user", [Content.from_uri(...), text])` and passes it to `Agent.run()` |

## Node Collapsing Patterns

The default mapping is **1 PF node → 1 MAF Executor**, and the graph topology must be preserved (see SKILL.md Rule 13). The patterns below are the **only** merges allowed. Any merge MUST be annotated in the Phase 1 node-mapping table with the pattern name (e.g., "Collapsed via: Prompt + LLM"). If a combination is not on this list, keep the nodes separate as 1:1 Executors — do not invent new merges.

### Allowed merges (closed list)

- **Prompt template + LLM node** → Merge into one Executor: extract system prompt to `Agent(instructions=...)`, format user prompt as a string with variables, then call `Agent.run()`
  - Example: `hello_prompt` (`.jinja2`) + `llm` (LLM) → single `LLMExecutor` with both template and agent
  - Required: the prompt node must feed *only* the LLM node (no other downstream consumers).
- **LLM + simple post-processing Python node** → Merge if post-processing is a few lines (e.g., extract substring, parse JSON, format output)
  - Required: post-processing is ≤ ~20 lines, has no external API calls, and the LLM node feeds *only* this post-processing node.
- **Static-data Python node** → Inline as module-level constant (e.g., `prepare_examples()`, `math_example()`) if data is <50 lines and the node has no inputs (pure constant producer).

### When to keep separate

- Node would need concurrent execution (e.g., two branches from the same source run in parallel)
- Post-processing is complex (>20 lines) or calls external APIs
- Output is consumed by multiple downstream nodes (keep it separate for clarity and reuse)
- Node has stateful side effects that should be isolated

### Example: Prompt + LLM collapse

```python
# Instead of two Executors:
class PromptExecutor(Executor):
    @handler
    async def receive(self, text: str, ctx: WorkflowContext[str]) -> None:
        prompt = f"Write a simple {text} program..."
        await ctx.send_message(prompt)

class LLMExecutor(Executor):
    @handler
    async def call_llm(self, prompt: str, ctx: WorkflowContext[Never, str]) -> None:
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)

# Can merge into one:
class PromptAndLLMExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agent = Agent(client=..., instructions=...)

    @handler
    async def generate(self, text: str, ctx: WorkflowContext[Never, str]) -> None:
        prompt = f"Write a simple {text} program..."
        response = await self._agent.run(prompt)
        await ctx.yield_output(response.text)
```
