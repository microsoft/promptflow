from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def echo_connection(flow_input: str, node_input: str, connection: AzureOpenAIConnection):
    print(f"Flow input: {flow_input}")
    print(f"Node input: {node_input}")
    print(f"Flow connection: {connection._to_dict()}")
    # get from env var
    return {"value": flow_input}
