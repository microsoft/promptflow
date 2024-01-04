try:
    from openai import AzureOpenAI as AzureOpenAIClient
except Exception:
    raise Exception(
        "Please upgrade your OpenAI package to version 1.0.0 or later using the command: pip install --upgrade openai.")

from promptflow._internal import ToolProvider, tool
from promptflow.connections import AzureOpenAIConnection
from promptflow.contracts.types import PromptTemplate
from typing import List, Dict
import requests

from promptflow.tools.common import render_jinja_template, handle_openai_error, parse_chat, \
    preprocess_template_string, find_referenced_image_set, convert_to_chat_list, normalize_connection_config, \
    post_process_chat_api_response

def list_versions() -> List[Dict[str, str]]:
    return ["version1", "version2"]


def list_deployment_names(subscription_id, resource_group_name, workspace_name, connection, version) -> List[Dict[str, str]]:
    from azure.identity import DefaultAzureCredential

    credential = DefaultAzureCredential()
    token = credential.get_token("https://management.azure.com/.default")

    url = (
        f"https://ml.azure.com/api/eastus2euap/flow/api/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/providers/"
        f"Microsoft.MachineLearningServices/workspaces/{workspace_name}/Connections/{connection}/AzureOpenAIDeployments"
    )
    result = requests.get(url, headers={"Authorization": f"Bearer {token.token}"})
    import json
    deployments = json.loads(result.text)
    
    deployment_names=[]
    for deployment in deployments:
        if(deployment.get("capabilities", {}).get("chat_completion", False)):
            name = deployment.get('name')
            cur_item = {
                "value": name,
                "display_value": name,
                "description": f"this is endpoint: {name}",
            }
            deployment_names.add(cur_item)

    return deployment_names


class AzureOpenAI(ToolProvider):
    def __init__(self, connection: AzureOpenAIConnection):
        super().__init__()
        self.connection = connection
        self._connection_dict = normalize_connection_config(self.connection)

        azure_endpoint = self._connection_dict.get("azure_endpoint")
        api_version = self._connection_dict.get("api_version")
        api_key = self._connection_dict.get("api_key")

        self._client = AzureOpenAIClient(azure_endpoint=azure_endpoint, api_version=api_version, api_key=api_key)    

    @tool(streaming_option_parameter="stream")
    @handle_openai_error()
    def chat(
        self,
        prompt: PromptTemplate,
        version: str,
        deployment_name: str,
        temperature: float = 1.0,
        top_p: float = 1.0,
        # stream is a hidden to the end user, it is only supposed to be set by the executor.
        stream: bool = False,
        stop: list = None,
        max_tokens: int = None,
        presence_penalty: float = 0,
        frequency_penalty: float = 0,
        **kwargs,
    ) -> str:
        # keep_trailing_newline=True is to keep the last \n in the prompt to avoid converting "user:\t\n" to "user:".
        prompt = preprocess_template_string(prompt)
        referenced_images = find_referenced_image_set(kwargs)

        # convert list type into ChatInputList type
        converted_kwargs = convert_to_chat_list(kwargs)
        chat_str = render_jinja_template(prompt, trim_blocks=True, keep_trailing_newline=True, **converted_kwargs)
        messages = parse_chat(chat_str, list(referenced_images))

        headers = {
            "Content-Type": "application/json",
            "ms-azure-ai-promptflow-called-from": "aoai-gpt4v-tool"
        }

        params = {
            "messages": messages,
            "temperature": temperature,
            "top_p": top_p,
            "n": 1,
            "stream": stream,
            "presence_penalty": presence_penalty,
            "frequency_penalty": frequency_penalty,
            "extra_headers": headers,
            "model": deployment_name,
        }

        if stop:
            params["stop"] = stop
        if max_tokens is not None:
            params["max_tokens"] = max_tokens

        completion = self._client.chat.completions.create(**params)
        return post_process_chat_api_response(completion, stream, None)
