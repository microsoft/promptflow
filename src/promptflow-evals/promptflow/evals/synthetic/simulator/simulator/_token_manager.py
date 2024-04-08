# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
from enum import Enum

from promptflow.evals.synthetic.simulator._model_tools import APITokenManager


class TokenScope(Enum):
    DEFAULT_AZURE_MANAGEMENT = "https://management.azure.com/.default"


class PlainTokenManager(APITokenManager):
    def __init__(self, openapi_key, logger, **kwargs):
        super().__init__(logger, **kwargs)
        self.token = openapi_key

    async def get_token(self):
        return self.token
