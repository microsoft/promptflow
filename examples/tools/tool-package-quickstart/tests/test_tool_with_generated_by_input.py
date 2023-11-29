import json
import pytest
import unittest

from my_tool_package.tools.tool_with_generated_by_input import (
    generate_index_json,
    list_embedding_deployment,
    list_fields,
    list_indexes,
    list_index_types,
    list_semantic_configuration,
    my_tool,
    reverse_generate_index_json,
)


@pytest.mark.parametrize("index_type", ["Azure Cognitive Search", "Workspace MLIndex"])
def test_my_tool(index_type):
    index_json = generate_index_json(index_type=index_type)
    result = my_tool(index_json, "", "")
    assert result == f'Hello {index_json}'


def test_generate_index_json():
    index_type = "Azure Cognitive Search"
    index_json = generate_index_json(index_type=index_type)
    indexes = json.loads(index_json)
    assert indexes["index_type"] == index_type


def test_reverse_generate_index_json():
    index_type = "Workspace MLIndex"
    index = list_indexes("", "", "")
    inputs = {
        "index_type": index_type,
        "index": index,
        "index_connection": "retrieved_index_connection",
        "index_name": "retrieved_index_name",
        "content_field": "retrieved_content_field",
        "embedding_field": "retrieved_embedding_field",
        "metadata_field": "retrieved_metadata_field",
        "semantic_configuration": "retrieved_semantic_configuration",
        "embedding_connection": "retrieved_embedding_connection",
        "embedding_deployment": "retrieved_embedding_deployment"
    }

    input_json = json.dumps(inputs)
    result = reverse_generate_index_json(input_json)
    for k, v in inputs.items():
        assert result[k] == v


def test_list_index_types():
    result = list_index_types("", "", "")
    assert isinstance(result, list)
    assert len(result) == 5


def test_list_indexes():
    result = list_indexes("", "", "")
    assert isinstance(result, list)
    assert len(result) == 10
    for item in result:
        assert isinstance(item, dict)


def test_list_fields():
    result = list_fields("", "", "")
    assert isinstance(result, list)
    assert len(result) == 9
    for item in result:
        assert isinstance(item, dict)


def test_list_semantic_configuration():
    result = list_semantic_configuration("", "", "")
    assert len(result) == 1
    assert isinstance(result[0], dict)


def test_list_embedding_deployment():
    result = list_embedding_deployment("")
    assert len(result) == 2
    for item in result:
        assert isinstance(item, dict)


if __name__ == "__main__":
    unittest.main()
