# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------


class ConnectionAuthMode:
    """Promptflow connection auth_mode values."""

    KEY = "key"
    MEID_TOKEN = "meid_token"  # Microsoft Entra ID


class ConnectionDefaultApiVersion:
    """Promptflow connection default api version values."""

    AZURE_OPEN_AI = "2024-02-01"
    COGNITIVE_SEARCH = "2023-11-01"
    AZURE_CONTENT_SAFETY = "2023-10-01"
    FORM_RECOGNIZER = "2023-07-31"
