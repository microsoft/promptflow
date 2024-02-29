
from promptflow import tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.entities import InputSetting, DynamicList
from typing import List, Dict
import requests


def list_deployment_names(subscription_id, resource_group_name, workspace_name, connection_name) -> List[Dict[str, str]]:
    """This is an example to show how to get Azure ML resource in tool input list function.

    :param subscription_id: Azure subscription id.
    :param resource_group_name: Azure resource group name.
    :param workspace_name: Azure ML workspace name.
    :param prefix: prefix to add to each item.
    """
    from azure.identity import DefaultAzureCredential
    from azure.ai.ml import MLClient

    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default")
    headers = {
        "Authorization": f"Bearer {token.token}"
    }

    ml_client = MLClient(credential=credential, subscription_id=subscription_id, resource_group_name=resource_group_name)
    workspace = ml_client.workspaces.get(workspace_name)
    region = workspace.location

    url = f"https://ml.azure.com/api/{region}/flow/api/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}/Connections/{connection_name}/AzureOpenAIDeployments"

    response = requests.get(url, headers=headers)
    response_json = response.json()

    output_dict = []

    for item in response_json:
        output_dict.append({"value": item["name"]})

    return output_dict


deployment_names_dynamic_list_setting = DynamicList(function=list_deployment_names, input_mapping={"connection_name": "connection"})


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool(input_settings={
    "deployment_name": InputSetting(
        dynamic_list=deployment_names_dynamic_list_setting,
        is_multi_select=False
    )})
def my_python_tool(connection: AzureOpenAIConnection, deployment_name: str) -> str:
    # llm call...
    return 'hello ' + deployment_name
