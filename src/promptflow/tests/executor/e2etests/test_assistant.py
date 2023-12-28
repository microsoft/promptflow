import json

import pytest
from openai import AsyncOpenAI
from openai.types import FunctionDefinition
from openai.types.beta.assistant import ToolFunction


@pytest.fixture
def cli(dev_connections):
    api_key = dev_connections.get("openai_config")["value"]["api_key"]
    cli_instance = AsyncOpenAI(api_key=api_key, organization="")
    return cli_instance


@pytest.mark.e2etest
@pytest.mark.asyncio
@pytest.mark.usefixtures("dev_connections")
class TestAssistant:
    async def test_simple(self, cli):
        assistant_id = "asst_eHO2rwEYqGH3pzzHHov2kBCG"
        assistant_obj = await cli.beta.assistants.retrieve(assistant_id=assistant_id)
        print("assistant name:" + assistant_obj.name + " retrieved")

        thread_id = "thread_hSirsQSw2kTbyCka2DTUTJj2"
        thread = await cli.beta.threads.retrieve(thread_id=thread_id)

        message_obj = await cli.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content="please generate a pie chart to compare the london VS nyc temperature.",
        )

        print(
            "message content: " + message_obj.content[0].text.value + "; " f"message count: {len(message_obj.content)}"
        )

        run_obj = await cli.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=assistant_id,
            instructions=assistant_obj.instructions,
            tools=[
                # {
                #     "type": "code_interpreter"
                # },
                {
                    "type": "function",
                    "function": {
                        "name": "get_calorie_by_jogging",
                        "description": "Estimate the calories burned by jogging based on duration and temperature.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "duration": {"description": "The length of the jogging in hours", "type": "number"},
                                "temperature": {
                                    "description": "The environment temperature in degrees Celsius",
                                    "type": "number",
                                },
                            },
                            "required": ["duration", "temperature"],
                        },
                    },
                },
            ],
        )

        print("-------tools involved------------")
        for tool in run_obj.tools:
            tool_type = tool.type
            tool_name = "code_interpreter"
            if hasattr(tool, "function"):
                tool_name = tool.function.name
            print(f"{tool_type} : {tool_name}")
        print("-------------------")

        while run_obj.status != "completed":
            run_obj = await cli.beta.threads.runs.retrieve(thread_id=thread_id, run_id=run_obj.id)
            print("status: " + run_obj.status)
            if run_obj.status == "requires_action":
                tool_calls = run_obj.required_action.submit_tool_outputs.tool_calls
                tool_outputs = []
                number = 12.3
                for tool_call in tool_calls:
                    print(f"requiring action tool: {tool_call.function.name}")
                    number += 1.7
                    tool_outputs.append(
                        {
                            "tool_call_id": tool_call.id,
                            "output": str(number),
                        }
                    )
                    await cli.beta.threads.runs.submit_tool_outputs(
                        thread_id=thread.id,
                        run_id=run_obj.id,
                        tool_outputs=tool_outputs,
                    )

        steps_obj = await cli.beta.threads.runs.steps.list(
            thread_id=thread_id,
            run_id=run_obj.id,
        )

        print("message creation: " + steps_obj.data[0].step_details.message_creation.message_id)

        created_message_obj = await cli.beta.threads.messages.retrieve(
            thread_id=thread_id, message_id=steps_obj.data[0].step_details.message_creation.message_id
        )

        print("output message: \n" + created_message_obj.content[0].text.value)

    def json_to_tool_function(self, json_data: str) -> ToolFunction:

        data = json.loads(json_data)
        function = FunctionDefinition(
            name=data["function"]["name"],
            description=data["function"]["description"],
            parameters=data["function"]["parameters"],
        )

        tool_function = ToolFunction(type=data["type"], function=function)

        return tool_function

    async def test_add_tools(self, cli):
        assistant_id = "asst_eHO2rwEYqGH3pzzHHov2kBCG"
        assistant_obj = await cli.beta.assistants.retrieve(assistant_id=assistant_id)
        tools = assistant_obj.tools
        new_tool = """
        {
            "type": "function",
            "function": {
                "name": "get_calorie_by_jogging",
                "description": "Estimate the calories burned by jogging based on duration and temperature.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "duration": {"description": "The length of the jogging in hours", "type": "number"},
                        "temperature": {"description": "The environment temperature in degrees Celsius",
                        "type": "number"}
                    },
                    "required": ["duration", "temperature"]
                }
            }
        }
        """

        new_f_function = self.json_to_tool_function(new_tool)
        tools.append(new_f_function)
        await cli.beta.assistants.update(assistant_id=assistant_id, tools=tools)
