from promptflow.core import tool
from promptflow.entities import InputSetting, DynamicList
from typing import List, Union, Dict


def my_list_func(prefix: str = "", size: int = 10, **kwargs) -> List[Dict[str, Union[str, int, float, list, Dict]]]:
    """This is a dummy function to generate a list of items.

    :param prefix: prefix to add to each item.
    :param size: number of items to generate.
    :param kwargs: other parameters.
    :return: a list of items. Each item is a dict with the following keys:
        - value: for backend use. Required.
        - display_value: for UI display. Optional.
        - hyperlink: external link. Optional.
        - description: information icon tip. Optional.
    """
    import random

    words = ["apple", "banana", "cherry", "date", "elderberry", "fig", "grape", "honeydew", "kiwi", "lemon"]
    result = []
    for i in range(size):
        random_word = f"{random.choice(words)}{i}"
        cur_item = {
            "value": random_word,
            "display_value": f"{prefix}_{random_word}",
            "hyperlink": f'https://www.bing.com/search?q={random_word}',
            "description": f"this is {i} item",
        }
        result.append(cur_item)

    return result


def list_endpoint_names(subscription_id, resource_group_name, workspace_name, prefix: str = "") -> List[Dict[str, str]]:
    """This is an example to show how to get Azure ML resource in tool input list function.

    :param subscription_id: Azure subscription id.
    :param resource_group_name: Azure resource group name.
    :param workspace_name: Azure ML workspace name.
    :param prefix: prefix to add to each item.
    """
    from azure.ai.ml import MLClient
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    credential.get_token("https://management.azure.com/.default")

    ml_client = MLClient(
        credential=credential,
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name)
    result = []
    for ep in ml_client.online_endpoints.list():
        hyperlink = (
            f"https://ml.azure.com/endpoints/realtime/{ep.name}/detail?wsid=/subscriptions/"
            f"{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft."
            f"MachineLearningServices/workspaces/{workspace_name}"
        )
        cur_item = {
            "value": ep.name,
            "display_value": f"{prefix}_{ep.name}",
            # external link to jump to the endpoint page.
            "hyperlink": hyperlink,
            "description": f"this is endpoint: {ep.name}",
        }
        result.append(cur_item)
    return result


input_text_dynamic_list_setting = DynamicList(function=my_list_func, input_mapping={"prefix": "input_prefix"})
endpoint_name_dynamic_list_setting = DynamicList(function=list_endpoint_names, input_mapping={"prefix": "input_prefix"})
input_settings = {
    "input_text": InputSetting(
        dynamic_list=input_text_dynamic_list_setting,
        allow_manual_entry=True,
        is_multi_select=True
    ),
    "endpoint_name": InputSetting(
        dynamic_list=endpoint_name_dynamic_list_setting,
        allow_manual_entry=False,
        is_multi_select=False
    )
}


@tool(
    name="My Tool with Dynamic List Input",
    description="This is my tool with dynamic list input",
    input_settings=input_settings
)
def my_tool(input_prefix: str, input_text: list, endpoint_name: str) -> str:
    return f"Hello {input_prefix} {','.join(input_text)} {endpoint_name}"
