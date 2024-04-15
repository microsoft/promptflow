import json
import os

import openai
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import time

from promptflow.tracing import trace, start_trace

from get_y import get_y

api_key = os.environ.get("aoai-api-key-eastus2")
api_base = os.environ.get("aoai-api-endpoint-eastus2")
api_version = os.environ.get("aoai-api-version", "2024-02-15-preview")
client = AsyncAzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=api_base,
)



async def get_or_create_assistant(assistant_id=None):
    if assistant_id:
        return await client.beta.assistants.retrieve(assistant_id)
    assistant_name = "Math Tutor"
    instruction = "You are a personal math tutor. Write and run code to answer math questions."
    model = "gpt-4"
    tools = [
        {"type": "code_interpreter"},
        {
            "type": "function",
            "function": {
                "name": "get_y",
                "description": "Return Y value based on input X value",
                "parameters": {
                    "type": "object",
                    "properties": {"x": {"description": "The X value", "type": "number"}},
                    "required": ["x"],
                },
            },
        }
    ]
    return await client.beta.assistants.create(
        name=assistant_name,
        instructions=instruction,
        model=model,
        tools=tools,
    )


async def get_or_create_thread(thread_id=None):
    if thread_id:
        return await client.beta.threads.retrieve(thread_id)
    return await client.beta.threads.create()

@trace
async def execute_run(thread_id, assistant_id):
    run = await client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    while True:
        time.sleep(1)  # Wait for 1 second
        run = await client.beta.threads.runs.poll(
            thread_id=thread_id,
            run_id=run.id
        )
        print(f"run status={run.status}")
        if run.status == "requires_action":
            await handle_require_actions(client, run)
        elif run.status in {"failed", "cancelled", "expired"}:
            if run.last_error is not None:
                error_message = f"The run {run.id} is in '{run.status}' status. " \
                                f"Error code: {run.last_error.code}. Message: {run.last_error.message}"
            else:
                error_message = f"The run {run.id} is in '{run.status}' status without a specific error message."
            raise Exception(error_message)
        elif run.status in {"completed"}:
            # Expect the terminated run to show up in trace
            return run
        else:
            raise Exception(f"Unsupported run status: {run.status}")


async def math_tutor(question: str, thread_id=None, assistant_id=None):
    await setup_async_trace()

    assistant = await get_or_create_assistant(assistant_id)

    thread = await get_or_create_thread(thread_id)

    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question
    )

    await execute_run(thread.id, assistant.id)

    return get_message(thread.id)



async def get_message(thread_id):
    messages = await client.beta.threads.messages.list(
        thread_id=thread_id
    )
    return [content.dict() for content in messages.data[0].content]

async def handle_require_actions(run):
    tool_outputs = await tool_calls(run)
    await client.beta.threads.runs.submit_tool_outputs(thread_id=run.thread_id, run_id=run.id, tool_outputs=tool_outputs)

@trace
async def tool_calls(run):
    tool_calls = run.required_action.submit_tool_outputs.tool_calls
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        print(f"Invoking tool: {tool_call.function.name} with args: {tool_args}")
        if tool_name == "get_y":
            output= get_y(**tool_args)
            print(f"Tool output: {str(output)}")
            tool_outputs.append(
                {
                    "tool_call_id": tool_call.id,
                    "output": str(output),
                }
            )
        else:
            raise Exception(f"Unexpected tool call: {tool_call.dict()}")
    return tool_outputs



async def setup_async_trace():
    openai.resources.beta.assistants.assistants.AsyncAssistants.create= trace(
        openai.resources.beta.assistants.assistants.AsyncAssistants.create)
    openai.resources.beta.threads.threads.AsyncThreads.create = trace(
        openai.resources.beta.threads.threads.AsyncThreads.create)
    openai.resources.beta.threads.messages.messages.AsyncMessages.create = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.create)
    openai.resources.beta.threads.runs.runs.AsyncRuns.create = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.create)
    openai.resources.beta.threads.messages.messages.AsyncMessages.list = trace(
        openai.resources.beta.threads.messages.messages.AsyncMessages.list)
    openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs = trace(
        openai.resources.beta.threads.runs.runs.AsyncRuns.submit_tool_outputs)
