# flake8: noqa
import os
from typing import Any, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from promptflow.evals.synthetic import TaskSimulator

openai_api_version = ""
api_key = ""
azure_endpoint = ""
azure_deployment = ""
subscription_id = ""
resource_group_name = ""
workspace_name = ""
index_name = ""
index_path = ""


os.environ["OPENAI_API_VERSION"] = openai_api_version
os.environ["AZURE_OPENAI_API_KEY"] = api_key
os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint

## define a callback that formats the interaction between the simulator and the rag application


async def callback(
    messages: List[Dict],
    stream: bool = False,
    session_state: Any = None,  # noqa: ANN401
    context: Optional[Dict[str, Any]] = None,
) -> dict:
    messages_list = messages["messages"]
    # get last message
    latest_message = messages_list[-1]
    query = latest_message["content"]
    context = None
    response_from_rag = {"answer": query, "context": None}
    # rag application responds with a dictionary containing the answer and context
    # we are formatting the response to follow the openAI chat protocol format
    formatted_response = {
        "content": response_from_rag["answer"],
        "role": "assistant",
        "context": {
            "citations": response_from_rag["context"],
        },
    }
    messages["messages"].append(formatted_response)
    return {"messages": messages["messages"], "stream": stream, "session_state": session_state, "context": context}


def get_info_for_context():

    import re

    from azureml.rag.mlindex import MLIndex

    # from azure.identity import DefaultAzureCredential
    from promptflow.rag.constants._common import STORAGE_URI_TO_MLINDEX_PATH_FORMAT

    def get_langchain_retriever_from_index(path: str):
        if re.match(STORAGE_URI_TO_MLINDEX_PATH_FORMAT, path):
            return MLIndex(path).as_langchain_retriever()

    from azure.ai.ml import MLClient

    client = MLClient(
        DefaultAzureCredential(),
        subscription_id=subscription_id,
        resource_group_name=resource_group_name,
        workspace_name=workspace_name,
    )

    index_langchain_retriever = get_langchain_retriever_from_index(path=index_path)

    docs = index_langchain_retriever.get_relevant_documents("Hiking boots?")
    import pdb

    pdb.set_trace()


text = get_info_for_context()
pf_azure_client = {
    "subscription_id": "",
    "resource_group_name": "",
    "project_name": "",
}
os.environ["AZURE_OPENAI_ENDPOINT"] = azure_endpoint
task_simulator = TaskSimulator(azure_ai_project=pf_azure_client, credential=DefaultAzureCredential())
outputs = task_simulator(target=callback, text=text, num_queries=5)
print(outputs)
import pdb

pdb.set_trace()
