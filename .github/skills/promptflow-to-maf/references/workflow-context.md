# WorkflowContext, Client & ChatOptions Reference

> Quick lookup for type annotations, LLM client selection, and chat parameters.
> Read this when writing Executor handlers or configuring LLM clients.

## WorkflowContext Type Parameters

| Annotation | Behaviour |
|---|---|
| `WorkflowContext` | Side effects only — no output sent |
| `WorkflowContext[str]` | Sends a `str` downstream via `ctx.send_message()` |
| `WorkflowContext[Never, str]` | Yields a `str` as the final workflow output via `ctx.yield_output()` |
| `WorkflowContext[str, str]` | Both sends downstream AND yields a workflow output |

`Never` is imported from `typing_extensions`.

---

## LLM Client Selection

| Scenario | Client | Constructor |
|----------|--------|-------------|
| Azure OpenAI (API key) | `OpenAIChatClient` | `OpenAIChatClient(azure_endpoint=..., model=..., api_key=...)` |
| Azure OpenAI (Entra ID) | `OpenAIChatClient` | `OpenAIChatClient(azure_endpoint=..., model=..., credential=DefaultAzureCredential())` |
| OpenAI (direct) | `OpenAIChatClient` | `OpenAIChatClient(model=..., api_key=...)` |
| Microsoft Foundry | `FoundryChatClient` | `FoundryChatClient(project_endpoint=..., model=..., credential=DefaultAzureCredential())` |

> `OpenAIChatClient` auto-routes to Azure when `azure_endpoint` is provided. There is no separate `AzureOpenAIChatClient` class.

---

## Chat Options (LLM Parameters)

Prompt Flow LLM nodes specify parameters like `temperature`, `max_tokens`, `top_p` in the YAML. In MAF, pass these via `OpenAIChatOptions` to `Agent.run()`:

```python
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions

# In the @handler method:
response = await self._agent.run(
    prompt,
    options=OpenAIChatOptions(temperature=0.2, max_tokens=128),
)
```

### Available Options

| Option | Type | Description |
|--------|------|-------------|
| `temperature` | `float` | Sampling temperature (0.0–2.0). Lower = more deterministic |
| `max_tokens` | `int` | Maximum tokens in the response |
| `top_p` | `float` | Nucleus sampling threshold |
| `stop` | `str \| Sequence[str]` | Stop sequences |
| `seed` | `int` | Deterministic sampling seed |
| `frequency_penalty` | `float` | Penalize repeated tokens |
| `presence_penalty` | `float` | Penalize tokens already present |
| `response_format` | `type[BaseModel] \| dict` | Structured output schema |
| `model` | `str` | Override the model for this call |
| `tool_choice` | `str` | Tool selection mode (`auto`, `required`, `none`) |

### Mapping from Prompt Flow YAML

| Prompt Flow LLM node field | `OpenAIChatOptions` field |
|---|---|
| `temperature: '0.2'` | `temperature=0.2` |
| `max_tokens: '128'` | `max_tokens=128` |
| `top_p: '1.0'` | `top_p=1.0` |
| `stop: ''` | (omit — empty means no stop sequence) |
| `frequency_penalty: '0'` | (omit — 0 is the default) |
| `presence_penalty: '0'` | (omit — 0 is the default) |

> Prompt Flow YAML stores these as strings (e.g., `'0.2'`). Convert to the appropriate numeric type in `OpenAIChatOptions`.

---

## Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `agent-framework` | >=1.0.1 (GA) | Core: `Executor`, `WorkflowBuilder`, `WorkflowContext`, `Agent`, `@handler` |
| `agent-framework-openai` | >=1.0.1 (GA) | `OpenAIChatClient`, `OpenAIChatOptions` — works for both OpenAI and Azure OpenAI |
| `agent-framework-foundry` | >=1.0.1 (GA) | `FoundryChatClient` — for Microsoft Foundry endpoints |
| `agent-framework-orchestrations` | preview | `HandoffBuilder` — for multi-agent handoffs |
| `agent-framework-azure-ai-search` | preview | `AzureAISearchContextProvider` — for RAG pipelines |
| `python-dotenv` | any | Load `.env` for credentials |
