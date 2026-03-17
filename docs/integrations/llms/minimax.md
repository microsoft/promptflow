# MiniMax

[MiniMax](https://www.minimaxi.com/) provides large language models accessible through an OpenAI-compatible API. This guide shows how to integrate MiniMax models into your prompt flow.

## Prerequisites

- A MiniMax API key from [MiniMax Platform](https://platform.minimaxi.com/)

## Available Models

| Model | Context Window | Description |
|-------|---------------|-------------|
| `MiniMax-M2.5` | 204K tokens | General-purpose model |
| `MiniMax-M2.5-highspeed` | 204K tokens | Faster variant for lower latency |

## Setup Connection

MiniMax uses an OpenAI-compatible API, so you can use prompt flow's built-in `OpenAIConnection` with a custom `base_url`.

### Using CLI

```bash
pf connection create -f minimax.yml --set api_key=<your-minimax-api-key>
```

Where `minimax.yml` contains:

```yaml
$schema: https://azuremlschemas.azureedge.net/promptflow/latest/OpenAIConnection.schema.json
name: minimax_connection
type: open_ai
api_key: "<user-input>"
base_url: "https://api.minimax.io/v1"
```

### Using Python SDK

```python
from promptflow.core import OpenAIModelConfiguration

config = OpenAIModelConfiguration(
    model="MiniMax-M2.5",
    base_url="https://api.minimax.io/v1",
    api_key="your-minimax-api-key",
)
```

### Using Environment Variables

```bash
export MINIMAX_API_KEY="your-api-key"
```

```python
import os
from promptflow.core import OpenAIModelConfiguration

config = OpenAIModelConfiguration(
    model="MiniMax-M2.5",
    base_url="https://api.minimax.io/v1",
    api_key=os.environ["MINIMAX_API_KEY"],
)
```

## Use in a Prompty File

```yaml
---
name: MiniMax Chat
model:
  api: chat
  configuration:
    type: openai
    model: MiniMax-M2.5
    base_url: https://api.minimax.io/v1
  parameters:
    temperature: 0.7
    max_tokens: 1024
---
```

## Use in a Flex Flow

```python
from promptflow.core import OpenAIModelConfiguration, Prompty
from promptflow.tracing import trace

config = OpenAIModelConfiguration(
    model="MiniMax-M2.5",
    base_url="https://api.minimax.io/v1",
    api_key="your-api-key",
)

prompty = Prompty.load(source="chat.prompty", model={"configuration": config})
result = prompty(question="Hello!")
```

## Notes

- **Temperature**: MiniMax accepts temperature values in the range `[0.0, 1.0]`.
- **Context window**: Both MiniMax-M2.5 models support up to 204K tokens.
- **Streaming**: Supported via the standard OpenAI streaming interface.

## Example

See the complete working example at [examples/flex-flows/chat-with-minimax](../../examples/flex-flows/chat-with-minimax/).
