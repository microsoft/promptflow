from dataclasses import dataclass
from promptflow import PFClient
from promptflow._sdk.entities._connection import CustomStrongTypeConnection


from promptflow.contracts.types import Secret
from promptflow._core.tools_manager import register_connections


class MyFirstConnection(CustomStrongTypeConnection):
    api_key: Secret
    api_hint: str = "This is my first connection."


register_connections([MyFirstConnection])


if __name__ == "__main__":
    # Get a pf client to manage connections
    pf = PFClient()

    # Initialize an AzureOpenAIConnection object
    connection = MyFirstConnection(
        name="fake_my_first_connection2",
        api_key="jefjwekfjlaskdjfe",
    )
    # Create the connection, note that api_key will be scrubbed in the returned result
    result = pf.connections.create_or_update(connection)
    print(result)