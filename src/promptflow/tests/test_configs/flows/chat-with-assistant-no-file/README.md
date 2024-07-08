# Chat with Calorie Assistant

This sample demonstrates how to chat with the PromptFlow Assistant tool facilitates calorie calculations by considering your location, the duration of your exercise, and the type of sport. Currently, it supports two types of sports: jogging and swimming.

Tools used in this flow：
- `add_message_and_run` tool, assistant tool, provisioned with below inner functions:
   - `get_current_location``: get current city
   - `get_temperature(location)``: get temperature of the city
   - `get_calorie_by_jogging(duration, temperature)``: calculate calorie for jogging exercise
   - `get_calorie_by_jogging(duration, temperature)``: calculate calorie for swimming exercise

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

Note in [flow.dag.yaml](flow.dag.yaml) we are using connection named `open_ai_connection`.
```bash
# show registered connection
pf connection show --name open_ai_connection
```

### 2. Create or get assistant/thread

Navigate to the OpenAI Assistant page and create an assistant if you haven't already. Once created, click on the 'Test' button to enter the assistant's playground. Make sure to note down the assistant_id.

**[Optional]** Start a chat session to create thread automatically. Keep track of the thread_id.


### 3. run the flow

```bash
# run chat flow with default question in flow.dag.yaml
pf flow test --flow . --interactive --multi-modal --user-agent "prompt-flow-extension/1.8.0 (win32; x64) VSCode/1.85.1"

```
