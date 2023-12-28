import asyncio
import json
from typing import Union

from openai import AsyncOpenAI
from openai.types.beta.threads import MessageContentImageFile, MessageContentText

from promptflow import tool
from promptflow.connections import OpenAIConnection
from promptflow.contracts.multimedia import Image
from promptflow.exceptions import SystemErrorException
from promptflow.executor.assistant_tool_invoker import AssistantToolInvoker

URL_PREFIX = "https://platform.openai.com/files/"


@tool
async def oai_assistant(
    conn: OpenAIConnection, content: Union[str, list], assistant_id: str, thread_id: str, assistant_definition: dict
):
    cli = AsyncOpenAI(api_key=conn.api_key, organization=conn.organization)
    if isinstance(content, str):
        prompt = content
        file_ids = []
    elif isinstance(content, list):
        prompt, file_ids = await convert_to_file_ids(content, cli)
    await cli.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt,
        file_ids=file_ids
    )
    invoker = AssistantToolInvoker()
    invoker.load_tools(assistant_definition["tools"])
    run = await cli.beta.threads.runs.create(
        thread_id=thread_id, assistant_id=assistant_id,
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
                output = invoker.invoke_tool(tool_call.function.name, json.loads(tool_call.function.arguments))
                tool_outputs.append({
                    "tool_call_id": tool_call.id,
                    "output": str(output),
                })
            await cli.beta.threads.runs.submit_tool_outputs(
                thread_id=thread_id,
                run_id=run.id,
                tool_outputs=tool_outputs,
            )
        elif run.status == "in_progress":
            continue
        else:
            raise Exception(f"The assistant tool runs in '{run.status}' status.")

    messages = await cli.beta.threads.messages.list(thread_id=thread_id)
    return await convert_content(messages.data[0].content, cli)


async def convert_to_file_ids(content: list, cli: AsyncOpenAI):
    prompt = ""
    file_ids = []
    for item in content:
        if item["type"] == "text":
            prompt += "\n" + item["text"]
        elif item["type"] == "file_path":
            path = item["file_path"]["path"]
            file = await cli.files.create(file=open(path, "rb"), purpose='assistants')
            file_ids.append(file.id)
    return prompt, file_ids


async def convert_content(content: list, cli: AsyncOpenAI):
    converted_content = []
    file_id_references = {}
    for item in content:
        if isinstance(item, MessageContentImageFile):
            file_id = item.image_file.file_id
            converted_content.append({"type": "image_file", "image_file": {"file_id": file_id}})
            file_id_references[file_id] = {"content": await download_image(file_id, cli), "url": URL_PREFIX + file_id}
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
                    file_id_references[annotation.file_path.file_id] = {
                        "url": URL_PREFIX + annotation.file_path.file_id
                    }
                elif annotation.type == "file_citation":
                    annotation_dict["file_citation"] = {"file_id": annotation.file_citation.file_id}
                    file_id_references[annotation.file_citation.file_id] = {
                        "url": URL_PREFIX + annotation.file_citation.file_id
                    }
                text_dict["text"]["annotations"].append(annotation_dict)
            converted_content.append(text_dict)
        else:
            raise SystemErrorException(f"Unsupported content type: {type(item)}")
    return {"content": converted_content, "file_id_references": file_id_references}


async def download_image(file_id: str, cli: AsyncOpenAI):
    image_data = await cli.files.content(file_id)
    image_data_bytes = image_data.read()
    image = Image(image_data_bytes)
    return image
