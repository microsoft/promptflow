# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from typing import TypedDict

from promptflow.core import AzureOpenAIModelConfiguration, OpenAIModelConfiguration


class FlowOutput(TypedDict):
    obj_input: str
    func_input: str
    obj_id: str


class MyFlow:
    def __init__(
            self,
            azure_open_ai_model_config: AzureOpenAIModelConfiguration,
            open_ai_model_config: OpenAIModelConfiguration
    ):
        self.azure_open_ai_model_config = azure_open_ai_model_config
        self.open_ai_model_config = open_ai_model_config

    def __call__(self, func_input: str) -> FlowOutput:
        return {
            "azure_open_ai_model_config_deployment": self.azure_open_ai_model_config.azure_deployment,
            "azure_open_ai_model_config_azure_endpoint": self.azure_open_ai_model_config.azure_endpoint,
            "azure_open_ai_model_config_connection": self.azure_open_ai_model_config.connection,
            "open_ai_model_config_model": self.open_ai_model_config.model,
            "open_ai_model_config_base_url": self.open_ai_model_config.base_url,
            "open_ai_model_config_connection": self.open_ai_model_config.connection,
            "func_input": func_input,
            "obj_id": id(self),
        }


if __name__ == "__main__":
    config1 = AzureOpenAIModelConfiguration(
        azure_deployment="my_deployment",
    )
    config2 = OpenAIModelConfiguration(
        model="my_model",
    )
    flow = MyFlow(azure_open_ai_model_config=config1, open_ai_model_config=config2)
    result = flow("func_input")
    print(result)

