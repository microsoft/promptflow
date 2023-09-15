from dataclasses import dataclass
from promptflow import PFClient
from promptflow.entities import AzureOpenAIConnection, CustomConnection


from promptflow.contracts.types import Secret
from promptflow._core.tools_manager import register_connections


@dataclass
class MyFirstConnection():
    api_key: Secret
    api_hint: str = "This is my first connection."


register_connections([MyFirstConnection])

if __name__ == "__main__":
    # Get a pf client to manage connections
    pf = PFClient()

    # Initialize an AzureOpenAIConnection object
    # connection = AzureOpenAIConnection(
    #     name="fake_azure_open_ai_connection",
    #     api_key="<your-api-key>",
    #     api_base="<your-endpoint>",
    #     api_version="2023-03-15-preview"
    # )
    # # Create the connection, note that api_key will be scrubbed in the returned result
    # result = pf.connections.create_or_update(connection)
    # print(result)

    # Initialize a custom connection objec
    connection = CustomConnection(
        name="my_custom_connection",
        # Secrets is a required field for custom connection
        secrets={"my_key": "<your-api-key>"},
        configs={"endpoint": "<your-endpoint>", "other_config": "other_value"}
    )

    # Create the connection, note that all secret values will be scrubbed in the returned result
    result = pf.connections.create_or_update(connection)
    print(result)