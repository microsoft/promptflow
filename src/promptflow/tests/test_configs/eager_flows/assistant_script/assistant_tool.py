import json
import os

import openai
from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
import time

from promptflow.tracing import trace, start_trace

from get_y import get_y


async def my_non_stream_assistant(assistant_name: str, instruction: str, model: str, question: str, tools: list[dict]=[]):
    await setup_async_trace()

    client = await get_client()

    tools.append({"type": "code_interpreter"})

    assistant = await client.beta.assistants.create(
        name=assistant_name,
        instructions=instruction,
        model=model,
    )

    thread = await client.beta.threads.create()

    message = await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=question
    )

    run = await client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=assistant.id,
        instructions=assistant.instructions,
        tools=tools,
    )

    while True:
        time.sleep(1)  # Wait for 1 second
        run = await client.beta.threads.runs.retrieve(
            thread_id=thread.id,
            run_id=run.id
        )
        print(f"run status={run.status}")
        if run.status == "requires_action":
            await handle_require_actions(client, run)
        elif run.status in {"in_progress", "cancelling", "queued"}:
            continue
        elif run.status in {"failed", "cancelled", "expired"}:
            if run.last_error is not None:
                error_message = f"The run {run.id} is in '{run.status}' status. " \
                                f"Error code: {run.last_error.code}. Message: {run.last_error.message}"
            else:
                error_message = f"The run {run.id} is in '{run.status}' status without a specific error message."
            raise Exception(error_message)
        else:
            # Run completed
            break

    messages = await client.beta.threads.messages.list(
        thread_id=thread.id
    )
    return [content.dict() for content in messages.data[0].content]

async def handle_require_actions(cli, run):
    tool_outputs = await get_tool_calls_outputs(run)
    await cli.beta.threads.runs.submit_tool_outputs(thread_id=run.thread_id, run_id=run.id, tool_outputs=tool_outputs)


async def get_tool_calls_outputs(run):
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

async def get_client():
    api_key = os.environ.get("aoai-api-key-eastus2")
    api_base = os.environ.get("aoai-api-endpoint-eastus2")
    api_version = os.environ.get("aoai-api-version", "2024-02-15-preview")
    client = AsyncAzureOpenAI(
            api_key=api_key,
            api_version=api_version,
            azure_endpoint=api_base,
        )
    return client


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
