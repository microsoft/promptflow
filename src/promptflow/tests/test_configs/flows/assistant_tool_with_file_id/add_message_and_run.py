import asyncio
import json

from openai import AsyncOpenAI
from openai.types.beta.threads import MessageContentImageFile, MessageContentText

from promptflow import tool
from promptflow.connections import OpenAIConnection
from promptflow.contracts.multimedia import Image
from promptflow.exceptions import SystemErrorException
from promptflow.executor.assistant_tool_invoker import AssistantToolInvoker

URL_PREFIX = "https://platform.openai.com/files/"


@tool
async def add_message_and_run(
    conn: OpenAIConnection,
    assistant_id: str,
    thread_id: str,
    message: list,
    assistant_definition: dict,
    download_images: bool
):
    content = extract_text_from_message(message)
    file_ids = await extract_file_ids_from_message(message, conn)
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    await cli.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=content,
        file_ids=file_ids
    )
    invoker = AssistantToolInvoker()
    invoker.load_tools(assistant_definition["tools"])
    run = await cli.beta.threads.runs.create(
        assistant_id=assistant_id,
        thread_id=thread_id,
        model = assistant_definition["model"],
        instructions=assistant_definition["instructions"],
        tools=invoker.to_openai_tools()
    )
    print(f"Assistant_id: {assistant_id}, thread_id: {thread_id}, run_id: {run.id}")

    while run.status != "completed":
        await asyncio.sleep(1)
        run = await cli.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run.id)
        print(f"Run status: {run.status}")
        if run.status == "requires_action":
            tool_calls = run.required_action.submit_tool_outputs.tool_calls
            tool_outputs = []
            for tool_call in tool_calls:
                print(f"Invoking tool: {tool_call.function.name}")
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)
                output = invoker.invoke_tool(tool_name, tool_args)
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": str(output),
                })
            await cli.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )
        elif run.status == "in_progress" or "completed":
            continue
        else:
            raise Exception(f"The assistant tool runs in '{run.status}' status.")

    messages = await cli.beta.threads.messages.list(thread_id=thread_id)
    file_id_references = await get_openai_file_references(messages.data[0].content, download_images, conn)
    return {"content": to_pf_content(messages.data[0].content), "file_id_references": file_id_references}


def extract_text_from_message(message: list):
    content = []
    for m in message:
        message_type = m.get("type", "")
        if message_type == "text" and "text" in m:
            content.append(m["text"])
    return "\n".join(content)


async def extract_file_ids_from_message(message: list, conn: OpenAIConnection):
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    file_ids = []
    for m in message:
        message_type = m.get("type", "")
        if  message_type == "file_path" and "file_path" in m:
            path = m["file_path"].get("path", "")
            if path:
                file = await cli.files.create(file=open(path, "rb"), purpose='assistants')
                file_ids.append(file.id)
    return file_ids


async def get_openai_file_references(content: list, download_image: bool, conn: OpenAIConnection):
    file_id_references = {}
    for item in content:
        if isinstance(item, MessageContentImageFile):
            file_id = item.image_file.file_id
            if download_image:
                file_id_references[file_id] = {
                    "content": await download_openai_image(file_id, conn), "url": URL_PREFIX + file_id
                }
            else:
                file_id_references[file_id] = {"url": URL_PREFIX + file_id}
        elif isinstance(item, MessageContentText):
            for annotation in item.text.annotations:
                if annotation.type == "file_path":
                    file_id = annotation.file_path.file_id
                    file_id_references[file_id] = {"url": URL_PREFIX + file_id}
                elif annotation.type == "file_citation":
                    file_id = annotation.file_citation.file_id
                    file_id_references[file_id] = {"url": URL_PREFIX + file_id}
        else:
            raise Exception(f"Unsupported content type: '{type(item)}'.")
    return file_id_references


def to_pf_content(content: list):
    pf_content = []
    for item in content:
        if isinstance(item, MessageContentImageFile):
            file_id = item.image_file.file_id
            pf_content.append({"type": "image_file", "image_file": {"file_id": file_id}})
        elif isinstance(item, MessageContentText):
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


async def download_openai_image(file_id: str, conn: OpenAIConnection):
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    image_data = await cli.files.content(file_id)
    return Image(image_data.read())
