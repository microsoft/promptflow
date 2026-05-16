# Custom-Tool Nodes (`source.type: package`)

> **Read this when** the source `flow.dag.yaml` contains a node with `source.type: package`.

A node whose `source.type` is `package` (rather than `code`) is a **user-defined PromptFlow tool**, not a stock LLM/Python node. The YAML looks like:

```yaml
- name: my_node
  type: python
  source:
    type: package
    tool: my_pkg.my_module.MyToolClass.my_function   # ← package-qualified tool path
  inputs:
    connection: my_connection
    prompt: ${upstream.output}
    model: my-internal-model-name
    # ...other tool-specific params declared by the tool's function signature
```

## Rule: keep the tool, replace only the runtime

Custom tools wrap functionality that MAF **does not provide**:
- Internal/proprietary LLM gateways (custom endpoints, auth, quota, batch routing)
- Domain-specific clients (search backends, vector stores, internal APIs)
- Org-specific connection types (`CustomConnection`, vendor SDK clients)
- Special headers, model-name conventions, segmentation, retry policies

**Re-pointing these calls to `OpenAIChatClient` / `Agent` silently changes the wire protocol, endpoint, model, auth, and quota system — and almost always breaks the deployment.** Even if the tool happens to wrap an OpenAI-compatible API, tool-specific parameters and behaviors (custom routing flags, quota tags, headers, model name conventions) will not survive the remap.

## Conversion steps

1. **Locate the tool implementation.** The `tool:` field is a Python import path. Open the source file and identify:
   - The class / function name (the last segment after the final `.`)
   - The class above it (second-to-last segment) — usually a `ToolProvider` subclass with a `@tool`-decorated method
   - Whether the `@tool` method delegates to a plain underlying class (very common pattern) — prefer calling that underlying class directly to drop the PromptFlow runtime dependency
2. **Read the function signature.** Note every parameter the YAML node passes, plus any defaults the tool applies internally (endpoints, headers, auth scopes, etc.).
3. **Inspect the connection object.** If the tool takes a `connection: CustomConnection`, find out where it reads its credentials. Many custom tools resolve credentials from environment variables (managed identity, AAD, client secret) and ignore the `connection` arg entirely — in which case pass `None` or omit it.
4. **Call the tool from inside an `Executor` `@handler`.** Instantiate the tool class once in `__init__` (so any credential/token caching is reused), then invoke it inside the handler.
5. **Wrap synchronous I/O in `asyncio.to_thread`.** Most custom tools are synchronous (they call `requests.post`, vendor SDKs, etc.). Calling them directly from an `async def` handler blocks the event loop — wrap them so other executors can run concurrently:
   ```python
   result = await asyncio.to_thread(self._tool, **tool_kwargs)
   ```
6. **Pass parameters verbatim from the YAML.** Copy every input from the node's `inputs:` block — including any tool-specific ones the original author added. Do not drop them; the tool's behavior may depend on them.
7. **Add the tool's package to `requirements.txt`.** If the tool lives in an in-repo package, document the install path (e.g., `pip install -e ../path/to/package`).
8. **Document credential env vars in `.env.example`.** Mirror whatever auth scheme the tool uses (managed identity, service principal, custom token endpoint).

## Example

Original PromptFlow node:

```yaml
- name: my_llm_call
  type: python
  source:
    type: package
    tool: my_pkg.tools.gateway.GatewayCompletion.completion
  inputs:
    connection: my_conn
    prompt: ${prompt_node.output}
    model: internal-model-v2
    max_tokens: 500
    temperature: 0
    # ...any other tool-specific params declared by the tool's signature
```

MAF Executor:

```python
import asyncio
from agent_framework import Executor, WorkflowContext, handler
from my_pkg.tools.gateway import GatewayCompletion   # the underlying class

class MyLLMExecutor(Executor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Instantiate once so token/credential caching is reused across calls.
        self._llm = GatewayCompletion()

    @handler
    async def call(self, prompt: str, ctx: WorkflowContext[str]) -> None:
        text = await asyncio.to_thread(
            self._llm,
            prompt=prompt,
            model="internal-model-v2",
            max_tokens=500,
            temperature=0,
            # ...forward every other input from the YAML node verbatim
        )
        await ctx.send_message(text)
```

## Anti-patterns

- ❌ Replacing the custom tool with `OpenAIChatClient` because "it's an LLM call too" — endpoint, auth, model names, and gateway-specific routing will all be wrong.
- ❌ Re-implementing the tool's HTTP request inline — duplicates auth/header/retry logic that the original tool already handles correctly.
- ❌ Importing the tool's `@tool`-decorated wrapper just to call it — pulls in PromptFlow as a runtime dependency. Prefer the underlying class.
- ❌ Calling the synchronous tool directly from an `async` handler — blocks the event loop and kills fan-out concurrency. Always wrap in `asyncio.to_thread`.
