import pytest

from promptflow.contracts.types import AssistantDefinition, FilePath, PromptTemplate, Secret


@pytest.mark.unittest
def test_secret():
    secret = Secret("my_secret")
    secret.set_secret_name("secret_name")
    assert secret.secret_name == "secret_name"


@pytest.mark.unittest
def test_prompt_template():
    prompt = PromptTemplate("my_prompt")
    assert isinstance(prompt, str)
    assert str(prompt) == "my_prompt"


@pytest.mark.unittest
def test_file_path():
    file_path = FilePath("my_file_path")
    assert isinstance(file_path, str)


@pytest.mark.unittest
def test_assistant_definition():
    data = {"model": "model", "instructions": "instructions", "tools": []}
    assistant_definition = AssistantDefinition.deserialize(data)
    assert isinstance(assistant_definition, AssistantDefinition)
    assert assistant_definition.model == "model"
    assert assistant_definition.instructions == "instructions"
    assert assistant_definition.tools == []
    assert assistant_definition.serialize() == data
    assert assistant_definition._tool_invoker is None
