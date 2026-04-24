# Basic Chat — Microsoft Agent Framework

This is the [Microsoft Agent Framework (MAF)](https://devblogs.microsoft.com/agent-framework/microsoft-agent-framework-version-1-0/) version of the [chat-basic](../chat-basic/) Prompt Flow example.

It implements the same behaviour: a helpful assistant chatbot that remembers conversation history and responds to user questions.

## Architecture

```
[InputExecutor] ──→ [ChatExecutor]
  (question +          (Agent with
   chat_history)        FoundryChatClient)
```

| Prompt Flow concept | MAF equivalent |
|---|---|
| `flow.dag.yaml` | `WorkflowBuilder` in `chat_flow.py` |
| `chat.jinja2` (system prompt) | `Agent(instructions="You are a helpful assistant.")` |
| LLM node (`api: chat`) | `FoundryChatClient` + `Agent.run()` |
| `chat_history` input | Message list assembled in `InputExecutor` |
| `open_ai_connection` | Environment variables (`FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`) + `DefaultAzureCredential` |

## Prerequisites

- Python 3.10+
- An Azure subscription with a Microsoft Foundry project (or Azure OpenAI resource)
- `az login` completed

## Setup

```bash
pip install -r requirements.txt

cp .env.example .env
# Edit .env with your Foundry project endpoint and model deployment name
```

## Run

```bash
python chat_flow.py
```

This runs two test interactions:
1. A single-turn question with no history
2. A follow-up question with one prior turn of chat history
