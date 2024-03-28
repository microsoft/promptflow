from typing import Union

from promptflow.core import tool
from typing import Dict, List
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection, CognitiveSearchConnection


def generate_index_json(
    index_type: str,
    index: str = "",
    index_connection: CognitiveSearchConnection = "",
    index_name: str = "",
    content_field: str = "",
    embedding_field: str = "",
    metadata_field: str = "",
    semantic_configuration: str = "",
    embedding_connection: Union[AzureOpenAIConnection, OpenAIConnection] = "",
    embedding_deployment: str = ""
) -> str:
    """This is a dummy function to generate a index json based on the inputs.
    """

    import json
    inputs = ""
    if index_type == "Azure Cognitive Search":
        # 1. Call to create a new index
        # 2. Call to get the index yaml and return as a json
        inputs = {
            "index_type": index_type,
            "index": "retrieved_index",
            "index_connection": index_connection,
            "index_name": index_name,
            "content_field": content_field,
            "embedding_field": embedding_field,
            "metadata_field": metadata_field,
            "semantic_configuration": semantic_configuration,
            "embedding_connection": embedding_connection,
            "embedding_deployment": embedding_deployment
        }
    elif index_type == "Workspace MLIndex":
        # Call to get the index yaml and return as a json
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

    result = json.dumps(inputs)
    return result


def reverse_generate_index_json(index_json: str) -> Dict:
    """This is a dummy function to generate origin inputs from index_json.
    """
    import json

    # Calculate the UI inputs based on the index_json
    result = json.loads(index_json)
    return result


def list_index_types(subscription_id, resource_group_name, workspace_name) -> List[str]:
    return [
        {"value": "Azure Cognitive Search"},
        {"value": "PineCone"},
        {"value": "FAISS"},
        {"value": "Workspace MLIndex"},
        {"value": "MLIndex from path"}
    ]


def list_indexes(
        subscription_id,
        resource_group_name,
        workspace_name
) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
    import random

    words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon"]
    result = []
    for i in range(10):
        random_word = f"{random.choice(words)}{i}"
        cur_item = {
            "value": random_word,
            "display_value": f"index_{random_word}",
            "hyperlink": f'https://www.bing.com/search?q={random_word}',
            "description": f"this is {i} item",
        }
        result.append(cur_item)

    return result


def list_fields(subscription_id, resource_group_name, workspace_name) -> List[str]:
    return [
        {"value": "id"},
        {"value": "content"},
        {"value": "catelog"},
        {"value": "sourcepage"},
        {"value": "sourcefile"},
        {"value": "title"},
        {"value": "content_hash"},
        {"value": "meta_json_string"},
        {"value": "content_vector_open_ai"}
    ]


def list_semantic_configuration(subscription_id, resource_group_name, workspace_name) -> List[str]:
    return [{"value": "azureml-default"}]


def list_embedding_deployment(embedding_connection: str) -> List[str]:
    return [{"value": "text-embedding-ada-002"}, {"value": "ada-1k-tpm"}]


@tool
def my_tool(index_json: str, queries: str, top_k: int) -> str:
    return f"Hello {index_json}"
