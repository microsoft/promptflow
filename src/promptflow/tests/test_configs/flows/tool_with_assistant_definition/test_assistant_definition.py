import os
from pathlib import Path

from promptflow import tool
from promptflow.contracts.types import AssistantDefinition
from promptflow.executor._assistant_tool_invoker import AssistantToolInvoker


@tool
def test_assistant_definition(message: str, assistant_definition: AssistantDefinition):
    assert assistant_definition.model == "mock_model"
    assert assistant_definition.instructions == "mock_instructions"
    assert len(assistant_definition.assistant_tools) == len(assistant_definition.tools) ==1
    invoker = AssistantToolInvoker.init(assistant_definition)
    openai_definition = invoker.to_openai_tools()
    assert len(openai_definition) == 1
    assert openai_definition[0]["function"]["description"] == "This tool is used to echo the message back."
    assert openai_definition[0]["function"]["parameters"]["properties"] == {
        "message": {"description": "The message to echo.", "type": "string"}
    }
    assert openai_definition[0]["function"]["parameters"]["required"] == ["message"]
    assert invoker.invoke_tool("echo", {"message": message}) == message
    return assistant_definition.serialize()
