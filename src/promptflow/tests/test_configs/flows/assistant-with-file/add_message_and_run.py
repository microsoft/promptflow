import asyncio
import json
from contextvars import ContextVar
from typing import Union, List
from openai.types.beta.threads.runs.code_interpreter_tool_call import CodeInterpreterOutput
from opentelemetry.trace import get_current_span
from openai.types.beta.threads import TextContentBlock, ImageFileContentBlock, Message
from promptflow.core import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection
from promptflow.contracts.multimedia import Image
from promptflow.contracts.types import AssistantDefinition
from promptflow.exceptions import SystemErrorException
from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker
from get_assistant_client import get_assistant_client
from promptflow.tracing import trace

URL_PREFIX = "https://platform.openai.com/files/"
RUN_STATUS_POLLING_INTERVAL_IN_MILSEC = 1000


cli_var: ContextVar[Union[AzureOpenAIConnection, OpenAIConnection]] = \
    ContextVar[Union[AzureOpenAIConnection, OpenAIConnection]]("cli_var", default=None)
tool_invoker_var: ContextVar[AssistantToolInvoker] = ContextVar[AssistantToolInvoker]("tool_invoker_var", default=None)
processed_steps_num_var: ContextVar[int] = ContextVar("processed_steps_num_var", default=0)

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
    cli_var.set(cli)
    invoker = assistant_definition._tool_invoker
    tool_invoker_var.set(invoker)
    processed_steps_num_var.set(0)
    # Check if assistant id is valid. If not, create a new assistant.
    # Note: tool registration at run creation, rather than at assistant creation.
    if not assistant_id:
        assistant = await create_assistant(assistant_definition)
        assistant_id = assistant.id

    await add_message(message, thread_id)

    run = await start_run(assistant_id, thread_id, assistant_definition)

    await wait_for_run_complete(thread_id, run.id)

    messages = await get_output_message(thread_id)

    file_id_references = await get_openai_file_references(messages.data[0].content, download_images, conn)
    return {"content": to_pf_content(messages.data[0].content), "file_id_references": file_id_references}


@trace
async def create_assistant(assistant_definition: AssistantDefinition):
    cli = cli_var.get()
    assistant = await cli.beta.assistants.create(
        instructions=assistant_definition.instructions, model=assistant_definition.model
    )
    print(f"Created assistant: {assistant.id}")
    return assistant


@trace
async def add_message(message: list, thread_id: str):
    content = extract_text_from_message(message)
    file_ids = await extract_file_ids_from_message(message)
    cli = cli_var.get()
    msg = await cli.beta.threads.messages.create(thread_id=thread_id, role="user", content=content, file_ids=file_ids)
    print(f"Created message message_id: {msg.id}, thread_id: {thread_id}")
    return msg


@trace
async def start_run(
        assistant_id: str,
        thread_id: str,
        assistant_definition: AssistantDefinition
):
    invoker = tool_invoker_var.get()
    tools = invoker.to_openai_tools()
    cli = cli_var.get()
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


async def get_run(thread_id: str, run_id: str):
    cli=cli_var.get()
    run = await cli.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_id)
    print(f"Run status: {run.status}")
    return run


async def get_tool_calls_outputs(run):
    tool_calls = run.required_action.submit_tool_outputs.tool_calls
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        print(f"Invoking tool: {tool_call.function.name} with args: {tool_args}")
        invoker=tool_invoker_var.get()
        output = invoker.invoke_tool(tool_name, tool_args)

        tool_outputs.append(
            {
                "tool_call_id": tool_call.id,
                "output": str(output),
            }
        )
        print(f"Tool output: {str(output)}")
    return tool_outputs

async def submit_tool_calls_outputs(thread_id: str, run_id: str,
                                    tool_outputs: list):
    cli=cli_var.get()
    await cli.beta.threads.runs.submit_tool_outputs(thread_id=thread_id, run_id=run_id, tool_outputs=tool_outputs)
    print(f"Submitted all required resonses for run: {run_id}")


@trace
async def require_actions(run):
    span=get_current_span()
    span.update_name("tool_calls [function]")
    tool_outputs = await get_tool_calls_outputs(run)
    await submit_tool_calls_outputs(run.thread_id, run.id, tool_outputs)



@trace
async def wait_for_run_complete(thread_id: str, run_id: str):
    while True:
        await wait_for_status_check()
        run = await get_run(thread_id, run_id)
        await process_new_completed_run_steps(thread_id, run)
        if run.status == "requires_action":
            await require_actions(run)
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




async def process_new_completed_run_steps(thread_id: str, run):
    cli=cli_var.get()
    run_steps = await cli.beta.threads.runs.steps.list(thread_id=thread_id, run_id=run.id)
    # Get all the completed run step since last processed point in time order
    processed_steps_num = processed_steps_num_var.get()
    for i in reversed(range(len(run_steps.data)-processed_steps_num)):
        if run_steps.data[i].status == "completed":
            processed_steps_num += 1
            if not (run_steps.data[i].type == "tool_calls" and run_steps.data[i].step_details.tool_calls[0].type == "function"):
                # Exclude tool_call with functions since the trace already created in require_actions
                await update_run_step_trace(run_steps.data[i])
    processed_steps_num_var.set(processed_steps_num)




@trace
async def update_run_step_trace(run_step):
    """Custom trace with run_step details"""
    # update trace name with run_step type
    span = get_current_span()
    span.update_name(run_step.type)
    cli = cli_var.get()
    if run_step.type == "message_creation":
        msg_id = run_step.step_details.message_creation.message_id
        message = await cli.beta.threads.messages.retrieve(message_id=msg_id, thread_id=run_step.thread_id)
        return convert_message_content(message.content)
    elif run_step.type == "tool_calls":
        if run_step.step_details.tool_calls[0].type == "code_interpreter":
            span.update_name(f"{run_step.type} [code_interpreter]")
            # assume code_interpreter only have one tool_call element
            tool_call = run_step.step_details.tool_calls[0]
            span.set_attribute("inputs", json.dumps(tool_call.code_interpreter.input))
            return convert_code_interpreter_outputs(tool_call.code_interpreter.outputs)
        elif run_step.step_details.type == "retrieval":
            # Todo: enrich this part after retrieval tool enabled in aoai
            span.update_name(f"{run_step.type} [retrieval]")
            return run_step
        else:
            pass


def convert_message_content(contents: List[Message]):
    return [content.dict() for content in contents]

def convert_code_interpreter_outputs(logs: List[CodeInterpreterOutput]):
    return [log.dict() for log in logs]


@trace
async def get_output_message(thread_id: str):
    cli=cli_var.get()
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


async def extract_file_ids_from_message(message: list):
    file_ids = []
    for m in message:
        if isinstance(m, str):
            continue
        message_type = m.get("type", "")
        if message_type == "file_path" and "file_path" in m:
            path = m["file_path"].get("path", "")
            if path:
                cli=cli_var.get()
                file = await cli.files.create(file=open(path, "rb"), purpose="assistants")
                file_ids.append(file.id)
    return file_ids


async def get_openai_file_references(content: list,
                                     download_image: bool,
                                     conn: Union[AzureOpenAIConnection, OpenAIConnection]):
    file_id_references = {}
    file_id = None
    for item in content:
        if isinstance(item, ImageFileContentBlock):
            file_id = item.image_file.file_id
            if download_image:
                file_id_references[file_id] = {
                    "content": await download_openai_image(file_id),
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


async def download_openai_image(file_id: str):
    cli=cli_var.get()
    image_data = await cli.files.content(file_id)
    return Image(image_data.read())

