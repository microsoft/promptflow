# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from promptflow._sdk.entities import AzureOpenAIConnection


class MyFlow:
    def __init__(self, obj_input: str, connection: AzureOpenAIConnection):
        self.obj_input = obj_input
        # connection will pass in as instance of AzureOpenAIConnection
        self.connection = connection

    def __call__(self, func_input: str) -> dict:
        return {
            "connection_api_type": self.connection.api_type,
            "obj_input": self.obj_input,
            "func_input": func_input,
            "obj_id": id(self),
        }


if __name__ == "__main__":
    flow = MyFlow("obj_input", connection=AzureOpenAIConnection.from_env())
    result = flow("func_input")
    print(result)

