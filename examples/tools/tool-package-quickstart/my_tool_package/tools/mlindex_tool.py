from promptflow import tool
from typing import List, Union, Dict
import requests
import json
from azure.identity import DefaultAzureCredential
import logging
import sys

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# create a stream handler
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)

# create a formatter and add it to the handler
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

# add the handler to the logger
logger.addHandler(handler)


def list_indexes(subscription_id, resource_group_name, workspace_name, keyword: str = "", 
                 index_type: str = "") -> List[Dict[str, str]]:
    """This is an example to show how to get Azure ML resource in tool input list function.

    :param subscription_id: Azure subscription id.
    :param resource_group_name: Azure resource group name.
    :param workspace_name: Azure ML workspace name.
    :param keyword: keyword to add to each item.
    """
    logger.debug(f"Start list_indexes function")
    credential = DefaultAzureCredential()
    # ml_client = MLClient(
    #     credential=credential,
    #     subscription_id=subscription_id,
    #     resource_group_name=resource_group_name,
    #     workspace_name=workspace_name)
    
    token = credential.get_token("https://management.azure.com/.default").token
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    # workspace level listing.
    # below is data plane api, need to change to use control plane api.
    url = f"https://ml.azure.com/api/eastus2euap/mlindex/v1.0/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}/mlindices?pageSize=1000"
    # url = "https://ml.azure.com/api/eastus2euap/mlindex/v1.0/subscriptions/96aede12-2f73-41cb-b983-6d11a904839b/resourceGroups/promptflow/providers/Microsoft.MachineLearningServices/workspaces/promptflow-gallery/mlindices?pageSize=1000"
    logger.debug(f"Start list_indexes url: {url}")
    response = requests.post(
        url,
        headers=headers,
        data=json.dumps([]),
        params={"pageSize": 1000}
        ).json()
    logger.debug(f"End list_indexes url: {url}")
    available_indices = [
        {
            "value": json.dumps(item),
            "display_value": item["name"],
            "hyperlink": f'https://ml.azure.com/prompts/vectorindex/{item["name"]}/{item["version"]}?wsid=/subscriptions/{subscription_id}/resourcegroups/{resource_group_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}',
            "description": f"this is {item['name']}"
        }
        # for item in response["value"] if item["status"] == "Ready" and keyword in item["name"]
        for item in response["value"] if keyword in item["name"]
    ]
    logger.debug(f"End list_indexes function")
    return available_indices


@tool
def my_tool(
    index_type: str, index: str, index_name_keyword: str, 
    acs_param: str, faiss_param: str, vector: list, top_k: int) -> str:
    return f"Hello {index}"
