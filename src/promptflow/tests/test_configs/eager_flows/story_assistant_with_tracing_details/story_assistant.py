import json
import random
import time

from openai.lib.azure import AsyncAzureOpenAI
from promptflow.tracing import trace
import os
from openai_injection import setup_trace
from openai import AzureOpenAI, NOT_GIVEN


############################################################################################################
# Injection code starts
############################################################################################################


setup_trace()

# This is a new span event for message_creation
@trace
def Message_creation(thread_id, message_id):
    return client.beta.threads.messages.retrieve(
        thread_id=thread_id,
        message_id=message_id
    )


@trace
def Code_interpreter(detail):
    pass


# This is an injected action to dump the run steps
# last_run_step_id should be managed in a session context or something like that.
last_run_step_id = NOT_GIVEN
def dump_run_steps(run):
    global last_run_step_id

    steps = client.beta.threads.runs.steps.list(run_id=run.id, thread_id=run.thread_id, order='asc', after=last_run_step_id)
    for step in steps:
        last_run_step_id = step.id
        if step.type == 'message_creation':
            message = Message_creation(
                thread_id=run.thread_id,
                message_id=step.step_details.message_creation.message_id
            )
            print(message)
        elif step.type == 'tool_calls':
            for tool_call in step.step_details.tool_calls:
                if tool_call.type == "code_interpreter":
                    Code_interpreter(tool_call.code_interpreter)







############################################################################################################
# User code starts
############################################################################################################


api_key = os.environ.get("aoai-api-key-eastus2")
api_base = os.environ.get("aoai-api-endpoint-eastus2")
api_version = os.environ.get("aoai-api-version", "2024-02-15-preview")
client = AsyncAzureOpenAI(
    api_key=api_key,
    api_version=api_version,
    azure_endpoint=api_base,
)


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



async def handle_require_actions(cli, run):
    tool_outputs = await tool_calls(run)
    await cli.beta.threads.runs.submit_tool_outputs(thread_id=run.thread_id, run_id=run.id, tool_outputs=tool_outputs)

@trace
async def tool_calls(run):
    tool_calls = run.required_action.submit_tool_outputs.tool_calls
    tool_outputs = []
    for tool_call in tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        print(f"Invoking tool: {tool_call.function.name} with args: {tool_args}")
        if tool_name == "get_character_counts":
            output = await get_character_counts(**tool_args)
        elif tool_name == "get_story_length":
            output = await get_story_length(**tool_args)
        else:
            raise Exception(f"Unexpected tool call: {tool_call.dict()}")
        tool_outputs.append(
            {
                "tool_call_id": tool_call.id,
                "output": str(output),
            }
        )
    return tool_outputs

@trace
async def get_character_counts():
    return json.dumps(random.randint(2, 4))


@trace
async def get_story_length(character_counts: int):
    return json.dumps(random.randint(50, 100))


async def get_or_create_assistant_1(assistant_id=None):
    if assistant_id is None:
        return await client.beta.assistants.create(
            name="Test assistant 1",
            instructions="You are an assistant to tell a story with the topic that provided by user. "
                         "Please make a simple beginning with no more than 20 words first. "
                         "Then use tools 'get_character_counts' and 'get_story_length' "
                         "to confirm more details and continue to complete this story.",
            model="gpt-35-turbo",
            tools=[
                {
                    "type": "function",
                    "function": {
                        "name": "get_character_counts",
                        "description": "Return the count of characters in the story.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                            },
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "get_story_length",
                        "description": "Return the length of total story in words",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "character_counts": {
                                    "type": "integer",
                                    "description": "The count of characters in the story",
                                },
                            },
                            "required": ["character_counts"],
                        }
                    },
                },
            ]
        )
    else:
        return await client.beta.assistants.retrieve(assistant_id=assistant_id)


async def get_or_create_assistant_2(assistant_id=None):
    if assistant_id is None:
        return await client.beta.assistants.create(
            name="Test assistant 2",
            instructions="You are an assistant to make an evaluation of the story you see. "
                         "And also write code to analyze the top keywords of this story.",
            model="gpt-4",
            tools=[
                {
                    "type": "code_interpreter"
                }
            ]
        )
    else:
        return await client.beta.assistants.retrieve(assistant_id=assistant_id)

async def get_message(thread_id, last_message_id: str=None):
    messages = await client.beta.threads.messages.list(
        thread_id=thread_id,
        after=last_message_id
    )
    return messages.data[0].id, [content.dict() for content in messages.data[0].content]

@trace
async def two_assistants_flow(topic: str):

    thread = await client.beta.threads.create()

    await client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=topic,
    )

    assistant_1 = await get_or_create_assistant_1(assistant_id="asst_3goNzF29uyirYXTPBL86xmq6")

    await execute_run(thread.id, assistant_1.id)
    msg_id, story = await get_message(thread.id)

    print("The first run is terminated")

    assistant_2 = await get_or_create_assistant_2(assistant_id="asst_GDAxTOkSn2mVFxXD1RdArEZl")

    await execute_run(thread.id, assistant_2.id)
    msg_id, evaluation = await get_message(thread.id, msg_id)

    print("The second run is terminated")

    return {
        "story": story,
        "evaluation": evaluation
    }

