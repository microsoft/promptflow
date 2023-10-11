# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from azure.core.credentials import AccessToken


class FakeTokenCredential:
    """Refer from Azure SDK for Python repository.

    https://github.com/Azure/azure-sdk-for-python/blob/main/tools/azure-sdk-tools/devtools_testutils/fake_credentials.py
    """

    def __init__(self):
        self.token = AccessToken("YOU SHALL NOT PASS", 0)
        self.get_token_count = 0

    def get_token(self, *args, **kwargs) -> AccessToken:
        self.get_token_count += 1
        return self.token
