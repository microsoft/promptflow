import asyncio
import json

from openai import AsyncOpenAI

from promptflow import tool
from promptflow.connections import OpenAIConnection
from promptflow.contracts.types import AssistantDefinition, PromptTemplate
from promptflow.executor._tool_invoker import AssistantToolInvoker


@tool
async def oai_assistant(conn: OpenAIConnection, content: PromptTemplate, assistant_id: str, assistant_definition: AssistantDefinition):
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    thread = await cli.beta.threads.create()
    await cli.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=content,
    )
    invoker = AssistantToolInvoker.load_tools(assistant_definition.tools)
    run = await cli.beta.threads.runs.create(
        thread_id=thread.id, assistant_id=assistant_id,
        instructions=assistant_definition.instructions,
        tools=invoker.to_openai_tools()
    )

    outputs = []
    while run.status != "completed":
        await asyncio.sleep(1)
        run = await cli.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        print(run.status)
        if run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            for tool_call in tool_calls:
                output = invoker.invoke_tool(tool_call.function.name, json.loads(tool_call.function.arguments))
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": str(output),
                })
                outputs.append({
                    "function": tool_call.function.name,
                    "arguments": tool_call.function.arguments,
                    "output": str(output)
                })
                await cli.beta.threads.runs.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
    return outputs
