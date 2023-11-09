from promptflow import tool
from typing import Dict, List


def generate_index_json(index_type: str = "", index: str = "", content_field: str = "", embedding_deployment="", **kwargs) -> str:
    """This is a dummy function to generate a index json from inputs.
    """

    import json
    inputs = {
        "index_type": index_type,
        "index": index,
        "content_field": content_field,
        "embedding_deployment": embedding_deployment,
    }
    inputs.update(kwargs)

    result = json.dumps(inputs)
    return result


def reverse_generate_index_json(index_json: str) -> Dict:
    """This is a dummy function to generate origin inputs from index_json.
    """
    import json

    result = json.loads(index_json)
    return result


def list_indexes(index_type: str) -> List[str]:
    result = []
    if index_type == "Azure Cognitive Search":
        result = ["0", "1"]
    elif index_type == "MLIndex":
        result = ["2", "3"]
    return result


def list_content_fields(index_type: str) -> List[str]:
    result = []
    if index_type == "Azure Cognitive Search":
        result = ["a", "b"]
    elif index_type == "MLIndex":
        result = ["c", "d"]
    return result


def list_embedding_deployment(index_type: str) -> List[str]:
    result = []
    if index_type == "Azure Cognitive Search":
        result = ["u", "v"]
    elif index_type == "MLIndex":
        result = ["x", "y"]
    return result


@tool
def my_tool(index_json: str, index_type: str, index_assetId: str, content_fields: str, embedding_deployment: str) -> str:
    return f"Hello {index_json}"
