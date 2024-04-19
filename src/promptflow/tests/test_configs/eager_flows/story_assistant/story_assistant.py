import json
import random
import time

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



# Inject the create_and_poll_run api with run steps dumping
def create_and_poll_run(thread_id, assistant_id):
    global last_run_step_id
    last_run_step_id = NOT_GIVEN

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    # This is an injected action to dump the run steps
    dump_run_steps(run)

    return run

# Inject the submit_tool_outputs_and_poll api with run steps dumping
def submit_tool_outputs_and_poll_run(thread_id, run_id, tool_outputs):
    run = client.beta.threads.runs.submit_tool_outputs_and_poll(
        thread_id=thread_id,
        run_id=run_id,
        tool_outputs=tool_outputs
    )

    dump_run_steps(run)

    return run


# We may want to provide help function or sample code to get messages in one run.
def get_messages_in_run(run):
    messages_in_run = []
    steps = client.beta.threads.runs.steps.list(run_id=run.id, thread_id=run.thread_id, order='asc')
    for step in steps:
        if step.usage is not None:
            print(step)
        if step.type == 'message_creation':
            message = client.beta.threads.messages.retrieve(
                thread_id=run.thread_id,
                message_id=step.step_details.message_creation.message_id
            )
            messages_in_run.append(message)
    return messages_in_run


def get_message(thread_id, last_message_id: str=None):
    messages = client.beta.threads.messages.list(
        thread_id=thread_id,
        after=last_message_id
    )
    return messages.data[0].id, [content.dict() for content in messages.data[0].content]


def  list_all_steps(run, thread_id):
    steps = client.beta.threads.runs.steps.list(run.id, thread_id=thread_id)
    for step in steps:
        print(step.dict())

############################################################################################################
# User code starts
############################################################################################################


client = AzureOpenAI(
    api_key=os.environ.get("aoai-api-key-eastus2"),
    api_version=os.environ.get("aoai-api-version", "2024-02-15-preview"),
    azure_endpoint=os.environ.get("aoai-api-endpoint-eastus2")
)


# We may want to introduce a decorator and span type for run execution here.
@trace
def Run_execute(thread_id, assistant_id):
    run =create_and_poll_run(
        thread_id=thread_id,
        assistant_id=assistant_id
    )

    while True:
        print(f"run status={run.status}")
        if run.status == "requires_action":
            tool_outputs = Tool_calls(required_tool_calls=run.required_action.submit_tool_outputs.tool_calls)
            run = submit_tool_outputs_and_poll_run(thread_id=run.thread_id, run_id=run.id, tool_outputs=tool_outputs)
        elif run.status in {"failed", "cancelled", "expired"}:
            if run.last_error is not None:
                error_message = f"The run {run.id} is in '{run.status}' status. " \
                                f"Error code: {run.last_error.code}. Message: {run.last_error.message}"
            else:
                error_message = f"The run {run.id} is in '{run.status}' status without a specific error message."
            raise Exception(error_message)
        elif run.status in {"completed"}:
            # Expect the terminated run to show up in trace
            # To delete: list all steps
            list_all_steps(run, thread_id)
            return run.dict()
        else:
            raise Exception(f"Unsupported run status: {run.status}")


# We may want to introduce a decorator and span type for tool_calls here.
@trace
def Tool_calls(required_tool_calls):
    tool_outputs = []
    for tool_call in required_tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        print(f"Invoking tool: {tool_call.function.name} with args: {tool_args}")
        if tool_name == "get_character_counts":
            output= get_character_counts(**tool_args)
        elif tool_name == "get_story_length":
            output = get_story_length(**tool_args)
        else:
            raise Exception(f"Unexpected tool call: {tool_call.dict()}")

        print(f"Tool output: {str(output)}")
        tool_outputs.append(
            {
                "tool_call_id": tool_call.id,
                "output": str(output),
            }
        )

    return tool_outputs


@trace
def get_character_counts():
    return random.randint(2, 4)


@trace
def get_story_length(character_counts: int):
    return random.randint(50, 100)


def get_or_create_assistant_1(assistant_id=None):
    if assistant_id is None:
        return client.beta.assistants.create(
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
        return client.beta.assistants.retrieve(assistant_id=assistant_id)


def get_or_create_assistant_2(assistant_id=None):
    if assistant_id is None:
        return client.beta.assistants.create(
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
        return client.beta.assistants.retrieve(assistant_id=assistant_id)


@trace
def two_assistants_flow(topic: str, assistant_1=None, assistant_2=None):

    thread = client.beta.threads.create()

    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=topic,
    )

    assistant_1 = get_or_create_assistant_1(assistant_1)

    Run_execute(thread.id, assistant_1.id)
    msg_id, story = get_message(thread.id)

    print(f"The first run complete")

    assistant_2 = get_or_create_assistant_2(assistant_2)

    Run_execute(thread.id, assistant_2.id)
    msg_id, evaluation = get_message(thread.id, msg_id)

    print(f"The second run complete")

    return {
        "story": story,
        "evaluation": evaluation
    }
