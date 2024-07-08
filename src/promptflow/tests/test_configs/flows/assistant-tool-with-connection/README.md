# Assistant Tool with Connection

This flow is used as example to illustrate how to use inner tool with connection in Assistant.

Tools used in this flow：
- `add_message_and_run` tool, assistant tool, provisioned with below inner functions:
   - `say_thanks``: express thanks statement


## Prerequisites

Install promptflow sdk and other dependencies in this folder:
```sh
pip install -r requirements.txt
```

## What you will learn

In this flow, you will understand how assistant tools within PromptFlow are triggered by user prompts. The assistant tool decides which internal functions or tools to invoke based on the input provided. Your responsibility involves implementing each of these tools and registering them in the `assistant_definition`. Additionally, be aware that the tools may have dependencies on each other, affecting the order and manner of their invocation.


## Getting started

### 1. Create assistant connection (openai)
Go to "Prompt flow" "Connections" tab. Click on "Create" button, select one of assistant tool supported connection types and fill in the configurations.

Currently, only "OpenAI" connection type are supported for assistant tool. Please refer to [OpenAI](https://platform.openai.com/) for more details.

```bash
# Override keys with --set to avoid yaml file changes
pf connection create --file ../../../connections/openai.yml --set api_key=<your_api_key>
```

Note:
1) In [flow.dag.yaml](flow.dag.yaml) we are using connection named `aoai_assistant_connection`.
```bash
# show registered connection
pf connection show --name aoai_assistant_connection
```
2) For aoai assistant, it works only in limited scope of connection support. Please refer to https://learn.microsoft.com/en-us/azure/ai-services/openai/how-to/assistant

### 2. Create or get assistant/thread

Navigate to the OpenAI Assistant page and create an assistant if you haven't already. Once created, click on the 'Test' button to enter the assistant's playground. Make sure to note down the assistant_id.

**[Optional]** Start a chat session to create thread automatically. Keep track of the thread_id.


### 3. run the flow

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow . --interactive --multi-modal --user-agent "prompt-flow-extension/1.8.0 (win32; x64) VSCode/1.85.1"

```
