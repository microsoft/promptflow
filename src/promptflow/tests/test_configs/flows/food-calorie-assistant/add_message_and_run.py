import asyncio
import json
from typing import Union, List

from openai import AsyncAzureOpenAI, AsyncOpenAI
from openai.types.beta.threads.runs.code_interpreter_tool_call import CodeInterpreterOutput

from openai.types.beta.threads.runs.tool_calls_step_details import ToolCall
from opentelemetry.trace import get_current_span

from get_tracer import get_tracer

from openai.types.beta.threads import TextContentBlock, ImageFileContentBlock, Message

from promptflow import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection
from promptflow.contracts.multimedia import Image
from promptflow.contracts.types import AssistantDefinition
from promptflow.exceptions import SystemErrorException
from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker
from get_assistant_client import get_assistant_client
from promptflow.tracing import trace

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
    tracer = await get_tracer()
    invoker = assistant_definition._tool_invoker
    # Check if assistant id is valid. If not, create a new assistant.
    # Note: tool registration at run creation, rather than at assistant creation.
    if not assistant_id:
        assistant = await create_assistant(cli, assistant_definition)
        assistant_id = assistant.id

    await add_message(cli, message, thread_id)

    run = await start_run(cli, assistant_id, thread_id, assistant_definition, invoker)

    await wait_for_run_complete(cli, thread_id, invoker, run, tracer)

    messages = await get_message(cli, thread_id)

    await list_run_steps(cli, thread_id, run.id, tracer)

    file_id_references = await get_openai_file_references(cli, messages.data[0].content, download_images, conn)
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



async def submit_tool_calls_outputs(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str,
                                    tool_outputs: list):
    await cli.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run_id, tool_outputs=tool_outputs)
    print(f"Submitted all required resonses for run: {run_id}")



async def require_actions(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run,
                          invoker: AssistantToolInvoker):
    tool_outputs = await get_tool_calls_outputs(invoker, run)
    await submit_tool_calls_outputs(cli, thread_id, run.id, tool_outputs)


@trace
async def wait_for_run_complete(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str,
                                invoker: AssistantToolInvoker, run, tracer):
    processed_steps_num= 0
    while not is_run_terminated(run):
        await wait_for_status_check()
        processed_steps_num = await get_new_run_steps(cli, thread_id, run.id, processed_steps_num, invoker, tracer)
        run = await get_run_status(cli, thread_id, run.id)
        if run.status == "requires_action":
            # We might get into this status since the run and run_step are managed separately.
            continue
        elif run.status in {"in_progress", "cancelling", "queued"}:
            continue
        elif run.status in {"failed", "cancelled", "expired"}:
            if run.last_error is not None:
                error_message = f"The assistant tool runs in '{run.status}' status. " \
                                f"Error code: {run.last_error.code}. Message: {run.last_error.message}"
            else:
                error_message = f"The assistant tool runs in '{run.status}' status without a specific error message."
            raise Exception(error_message)



async def get_new_run_steps(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str, processed_steps_num: int, invoker: AssistantToolInvoker, tracer):
    run_steps = await cli.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id)
    # Todo: For now, assume the step are completed sequentially;
    # Actually it might be concurrently. Do some research and change later
    for i in reversed(range(len(run_steps.data))):
        if i < len(run_steps.data) - processed_steps_num:
            await wait_for_run_step_complete(cli, thread_id, run_id, run_steps.data[i].id, invoker, tracer)
    processed_steps_num = len(run_steps.data)
    return processed_steps_num

@trace
async def wait_for_run_step_complete(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str, run_step_id: str, invoker: AssistantToolInvoker, tracer):
    span = get_current_span()
    step_run = await cli.beta.threads.runs.steps.retrieve(thread_id=thread_id, run_id=run_id, step_id=run_step_id)
    span.update_name(step_run.type)
    while not is_run_terminated(step_run):
        run = await get_run_status(cli, thread_id, run_id)
        if run.status == "requires_action":
            await require_actions(cli, thread_id, run, invoker)
        await wait_for_status_check()
        step_run = await cli.beta.threads.runs.steps.retrieve(thread_id=thread_id, run_id=run_id, step_id=run_step_id)
        #todo: Research if action on other status here

    # trace enrichment
    if step_run.status == "completed":
        if step_run.type == "message_creation":
            msg_id = step_run.step_details.message_creation.message_id
            await message(cli, thread_id, msg_id)
        elif step_run.type == "tool_calls":
            if step_run.step_details.tool_calls[0].type == "code_interpreter":
                await trace_code_interpreter(step_run, tracer)
            elif step_run.step_details.type == "retrieval":
                pass
        else:
            pass
    else:
        #Todo: enrich this logic
        pass

    return step_run

@trace
async def message(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, msg_id: str):
    message = await cli.beta.threads.messages.retrieve(message_id=msg_id, thread_id=thread_id)
    return convert_message_content(message.content)

async def trace_code_interpreter(step_run, tracer):
    tool_call = step_run.step_details.tool_calls[0]
    with tracer.start_as_current_span(tool_call.type, start_time=_to_nano(step_run.created_at), end_on_exit=False) as span:
        span.set_attribute("inputs", json.dumps(tool_call.code_interpreter.input))
        span.set_attribute("output", json.dumps(convert_code_interpreter_outputs(tool_call.code_interpreter.outputs)))
        span.end(end_time=_to_nano(step_run.completed_at))
    return tool_call



@trace
async def list_run_steps(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], thread_id: str, run_id: str, tracer):
    run_steps = await cli.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run_id)
    step_runs = []
    for run_step in run_steps.data:
        step_runs.append(run_step.dict())
        await show_run_step(cli, run_step, tracer)
    return step_runs


async def show_run_step(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], run_step, tracer):
    with tracer.start_as_current_span(run_step.type, start_time=_to_nano(run_step.created_at), end_on_exit=False) as span:
        if run_step.type == "message_creation":
            msg_id = run_step.step_details.message_creation.message_id
            message = await cli.beta.threads.messages.retrieve(message_id=msg_id, thread_id=run_step.thread_id)
            span.set_attribute("output", json.dumps(convert_message_content(message.content)))
            span.set_attribute("msg_id", msg_id)
            span.set_attribute("role", message.role)
            span.set_attribute("created_at", message.created_at)
        elif run_step.type == "tool_calls":
            for tool_call in run_step.step_details.tool_calls:
                await show_tool_call(tool_call, tracer)
            span.set_attribute("output", json.dumps(convert_tool_calls(run_step.step_details.tool_calls)))
        span.set_attribute("thread_id", run_step.thread_id)
        span.end(end_time=_to_nano(run_step.completed_at))
    return run_step

def convert_message_content(contents: List[Message]):
    return [content.dict() for content in contents]

def convert_tool_calls(calls: List[ToolCall]):
    return [call.dict() for call in calls]

def _to_nano(unix_time_in_sec: int):
    """Convert Unix timestamp from seconds to nanoseconds."""
    return unix_time_in_sec*1000000000

async def show_tool_call(tool_call, tracer):
    #Todo: start_time and end_time are not avaliable in tool_call. Shall fullfill it later.
    if tool_call.type == "code_interpreter":
        span_name = "code_interpreter"
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("inputs", json.dumps(tool_call.code_interpreter.input))
            span.set_attribute("output", json.dumps(convert_code_interpreter_outputs(tool_call.code_interpreter.outputs)))
    elif tool_call.type == "function":
        span_name=tool_call.function.name
        with tracer.start_as_current_span(span_name) as span:
            span.set_attribute("inputs", tool_call.function.arguments)
            span.set_attribute("output", json.dumps(tool_call.function.output))
    else:
        span_name = "retrieval"
        with tracer.start_as_current_span(span_name) as span:
            # todo: fulfill after retrieval tool enabled in aoai
            pass
    return tool_call


def convert_code_interpreter_outputs(logs: List[CodeInterpreterOutput]):
    return [log.dict() for log in logs]


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


async def get_openai_file_references(cli: Union[AsyncOpenAI, AsyncAzureOpenAI],
                                     content: list,
                                     download_image: bool,
                                     conn: Union[AzureOpenAIConnection, OpenAIConnection]):
    file_id_references = {}
    file_id = None
    for item in content:
        if isinstance(item, ImageFileContentBlock):
            file_id = item.image_file.file_id
            if download_image:
                file_id_references[file_id] = {
                    "content": await download_openai_image(cli, file_id, conn),
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


async def download_openai_image(cli: Union[AsyncOpenAI, AsyncAzureOpenAI], file_id: str,
                                conn: Union[AzureOpenAIConnection, OpenAIConnection]):
    image_data = await cli.files.content(file_id)
    return Image(image_data.read())


def is_run_terminated(run) -> bool:
    return run.status in ["completed", "expired", "failed", "cancelled"]
