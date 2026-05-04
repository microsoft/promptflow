# Gotchas — Common Pitfalls When Converting Prompt Flow to MAF

> Read this every time you generate or debug MAF code. These are mistakes the agent makes repeatedly.

## High-frequency (almost always relevant)

### 1. `Agent.run()` returns `AgentResponse`, not `str`
Always use `response.text` to get the string output, then pass that to `ctx.yield_output()`.

### 2. No `AzureOpenAIChatClient` class
Use `OpenAIChatClient` with `azure_endpoint=...` for Azure routing.

### 3. `@handler` message type must match upstream
If the upstream executor sends a `str` via `ctx.send_message(str)`, the downstream `@handler` parameter must be typed as `str`.

### 4. Never name a `@handler` method `execute`
The base `Executor` class has an `execute()` method that the workflow engine calls with internal arguments (`message`, `source_executor_ids`, `state`, `runner_context`, `trace_contexts`, `source_span_ids`). If a subclass defines a `@handler` method also named `execute`, it shadows the base method, causing `TypeError: got an unexpected keyword argument 'trace_contexts'` at runtime. Use any other name (e.g., `run_code`, `process`, `handle`, `invoke`).

### 5. MAF workflows do not support concurrent `run()` calls
Calling `workflow.run()` on an instance that is already running throws `RuntimeError: Workflow is already running. Concurrent executions are not allowed.` Always export a `create_workflow()` factory function and create a fresh instance per invocation. This applies to **all** workflows — not just evaluation flows — so callers can safely parallelize.

### 6. Preserve LLM parameters from the original flow
If the Prompt Flow YAML sets `temperature`, `max_tokens`, etc. on an LLM node, these MUST be carried over to the MAF `Agent.run()` call via `OpenAIChatOptions`. Omitting them changes model behavior (e.g., higher temperature = less deterministic outputs, missing `max_tokens` = truncated/verbose responses).

### 7. LLM responses wrapped in markdown fences
Modern LLMs often wrap JSON output in ` ```json ... ``` ` code fences even when not asked to. When parsing JSON from `Agent.run()` responses, always strip markdown fences before calling `json.loads()`:

```python
text = response.text.strip()
if text.startswith("```"):
    text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
result = json.loads(text)
```

Without this, `json.loads()` raises `JSONDecodeError` and the fallback silently returns wrong results.

---

## Mid-frequency (situation-specific)

### 8. Chat history cannot be passed as `list[dict]` to `Agent.run()`
Format it into a single prompt string instead.

### 9. Fan-in delivers `list[T]`
The aggregator's `@handler` receives a list of all upstream messages.

### 10. Condition functions receive the message
`condition=fn` where `fn(message) -> bool`.

### 11. Environment variables auto-read
`OpenAIChatClient` can auto-read `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_CHAT_MODEL` from env, but explicit constructor args are clearer.

### 12. Internal package imports
When a flow imports from sibling Python packages (e.g., `from my_utils.helpers import build_index`), copy the entire package directory into the MAF output folder. Do not rewrite utility code. The Executor files import directly from the local copy since they live in the same directory. Do not use `sys.path` hacks.

---

## Topic-specific (only when applicable)

### 13. Multimodal inputs require `Message`, not `str`
When a flow has image inputs (e.g., GPT-4V), you must build a `Message("user", [Content.from_uri(...), "text"])` and pass it to `Agent.run()`. Joining image URLs into a plain string will NOT send the image to the model. See [topics/multimodal.md](../topics/multimodal.md).

### 14. Prompt Flow image format — handle both forms
Prompt Flow image inputs come in two formats:
- **Dict format** (from CLI): `{"data:image/png;url": "https://example.com/img.png"}` — extract the URL from the dict value
- **String format** (from YAML defaults): `"data:image/png;url: https://example.com/img.png"` — parse the URL after `url: `

Both must be converted to `Content.from_uri(url, media_type="image/png")`.

### 15. Evaluation aggregation functions must return a dict
The original PromptFlow aggregation nodes call `log_metric(key, value)` to report metrics. In MAF, replace these with a returned `dict` mapping metric names to values. Remove all `log_metric` imports and calls. See [topics/evaluation-flows.md](../topics/evaluation-flows.md).
