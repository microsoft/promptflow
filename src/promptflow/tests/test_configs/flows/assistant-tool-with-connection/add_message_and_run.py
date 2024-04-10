import asyncio
import json
from typing import Union

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.beta.threads import TextContentBlock, ImageFileContentBlock

from promptflow.core import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection
from promptflow.contracts.multimedia import Image
from promptflow.contracts.types import AssistantDefinition
from promptflow.exceptions import SystemErrorException
from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker
from promptflow.tracing import trace

from get_assistant_client import get_assistant_client

URL_PREFIX = "https://platform.openai.com/files/"
RUN_STATUS_POLLING_INTERVAL_IN_MILSEC = 1000


@tool
async def add_message_and_run(
        conn: Union[AzureOpenAIConnection, OpenAIConnection],
        assistant_id: str,
        thread_id: str,
        message: list,
        assistant_definition: AssistantDefinition,
        download_images: bool,
):
    cli = await get_assistant_client(conn)
    invoker = assistant_definition._tool_invoker
    # Check if assistant id is valid. If not, create a new assistant.
    # Note: tool registration at run creation, rather than at assistant creation.
    if not assistant_id:
        assistant = await create_assistant(cli, assistant_definition)
        assistant_id = assistant.id

    await add_message(cli, message, thread_id)

    run = await start_run(cli, assistant_id, thread_id, assistant_definition, invoker)

    await wait_for_run_complete(cli, thread_id, invoker, run)

    messages = await get_message(cli, thread_id)

    file_id_references = await get_openai_file_references(messages.data[0].content, download_images, conn)
    return {"content": to_pf_content(messages.data[0].content), "file_id_references": file_id_references}


@trace
async def create_assistant(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], assistant_definition: AssistantDefinition):
    assistant = await cli.beta.assistants.create(
        instructions=assistant_definition.instructions, model=assistant_definition.model
    )
    print(f"Created assistant: {assistant.id}")
    return assistant


@trace
async def add_message(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], message: list, thread_id: str):
    content = extract_text_from_message(message)
    file_ids = await extract_file_ids_from_message(cli, message)
    msg = await cli.beta.threads.messages.create(thread_id=thread_id, role="user", content=content, file_ids=file_ids)
    print(f"Created message message_id: {msg.id}, thread_id: {thread_id}")
    return msg


@trace
async def start_run(
        cli: Union[AsyncOpenAI, AsyncAzureOpenAI],
        assistant_id: str,
        thread_id: str,
        assistant_definition: AssistantDefinition,
        invoker: AssistantToolInvoker,
):
    tools = invoker.to_openai_tools()
    run = await cli.beta.threads.runs.create(
        assistant_id=assistant_id,
        thread_id=thread_id,
        model=assistant_definition.model,
        instructions=assistant_definition.instructions,
        tools=tools,
    )
    print(f"Assistant_id: {assistant_id}, thread_id: {thread_id}, run_id: {run.id}")
    return run


async def wait_for_status_check():
    await asyncio.sleep(RUN_STATUS_POLLING_INTERVAL_IN_MILSEC / 1000.0)


async def get_run_status(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str):
    run = await cli.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    print(f"Run status: {run.status}")
    return run


@trace
async def get_tool_calls_outputs(invoker: AssistantToolInvoker, run):
    tool_calls = run.required_action.submit_tool_outputs.tool_calls
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        print(f"Invoking tool: {tool_call.function.name} with args: {tool_args}")
        output = invoker.invoke_tool(tool_name, tool_args)

        tool_outputs.append(
            {
                "tool_call_id": tool_call.id,
                "output": str(output),
            }
        )
        print(f"Tool output: {str(output)}")
    return tool_outputs


@trace
async def submit_tool_calls_outputs(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str,
                                    tool_outputs: list):
    await cli.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run_id, tool_outputs=tool_outputs)
    print(f"Submitted all required resonses for run: {run_id}")


@trace
async def require_actions(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run,
                          invoker: AssistantToolInvoker):
    tool_outputs = await get_tool_calls_outputs(invoker, run)
    await submit_tool_calls_outputs(cli, thread_id, run.id, tool_outputs)


@trace
async def wait_for_run_complete(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str,
                                invoker: AssistantToolInvoker, run):
    while not is_run_terminated(run):
        await wait_for_status_check()
        run = await get_run_status(cli, thread_id, run.id)
        if run.status == "requires_action":
            await require_actions(cli, thread_id, run, invoker)
        elif run.status in {"in_progress", "cancelling", "queued"}:
            continue
        elif run.status in {"failed", "cancelled", "expired"}:
            if run.last_error is not None:
                error_message = f"The assistant tool runs in '{run.status}' status. " \
                                f"Error code: {run.last_error.code}. Message: {run.last_error.message}"
            else:
                error_message = f"The assistant tool runs in '{run.status}' status without a specific error message."
            raise Exception(error_message)


@trace
async def get_run_steps(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str):
    run_steps = await cli.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id)
    print("step details: \n")
    for step_data in run_steps.data:
        print(step_data.step_details)


@trace
async def get_message(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str):
    messages = await cli.beta.threads.messages.list(thread_id=thread_id)
    return messages


def extract_text_from_message(message: list):
    content = []
    for m in message:
        if isinstance(m, str):
            content.append(m)
            continue
        message_type = m.get("type", "")
        if message_type == "text" and "text" in m:
            content.append(m["text"])
    return "\n".join(content)


async def extract_file_ids_from_message(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], message: list):
    file_ids = []
    for m in message:
        if isinstance(m, str):
            continue
        message_type = m.get("type", "")
        if message_type == "file_path" and "file_path" in m:
            path = m["file_path"].get("path", "")
            if path:
                file = await cli.files.create(file=open(path, "rb"), purpose="assistants")
                file_ids.append(file.id)
    return file_ids


async def get_openai_file_references(content: list, download_image: bool,
                                     conn: Union[AzureOpenAIConnection, OpenAIConnection]):
    file_id_references = {}
    file_id = None
    for item in content:
        if isinstance(item, ImageFileContentBlock):
            file_id = item.image_file.file_id
            if download_image:
                file_id_references[file_id] = {
                    "content": await download_openai_image(file_id, conn),
                }
        elif isinstance(item, TextContentBlock):
            for annotation in item.text.annotations:
                if annotation.type == "file_path":
                    file_id = annotation.file_path.file_id
                elif annotation.type == "file_citation":
                    file_id = annotation.file_citation.file_id
        else:
            raise Exception(f"Unsupported content type: '{type(item)}'.")

        if file_id:
            if file_id not in file_id_references:
                file_id_references[file_id] = {}
            if isinstance(conn, OpenAIConnection):
                file_id_references[file_id]["url"] = URL_PREFIX + file_id
            else:
                # For AzureOpenAIConnection, the url is not avaliable. Shall fullfill it later.
                pass
    return file_id_references


def to_pf_content(content: list):
    pf_content = []
    for item in content:
        if isinstance(item, ImageFileContentBlock):
            file_id = item.image_file.file_id
            pf_content.append({"type": "image_file", "image_file": {"file_id": file_id}})
        elif isinstance(item, TextContentBlock):
            text_dict = {"type": "text", "text": {"value": item.text.value, "annotations": []}}
            for annotation in item.text.annotations:
                annotation_dict = {
                    "type": "file_path",
                    "text": annotation.text,
                    "start_index": annotation.start_index,
                    "end_index": annotation.end_index,
                }
                if annotation.type == "file_path":
                    annotation_dict["file_path"] = {"file_id": annotation.file_path.file_id}
                elif annotation.type == "file_citation":
                    annotation_dict["file_citation"] = {"file_id": annotation.file_citation.file_id}
                text_dict["text"]["annotations"].append(annotation_dict)
            pf_content.append(text_dict)
        else:
            raise SystemErrorException(f"Unsupported content type: {type(item)}")
    return pf_content


async def download_openai_image(file_id: str, conn: Union[AzureOpenAIConnection, OpenAIConnection]):
    cli = await get_assistant_client(conn)
    image_data = await cli.files.content(file_id)
    return Image(image_data.read())


def is_run_terminated(run) -> bool:
    return run.status in ["completed", "expired", "failed", "cancelled"]