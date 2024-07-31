# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------

from enum import Enum

BOT_NAMES = ["chat_bot", "other_bot"]
TASK_BOT_NAMES = ["system_bot", "simulated_bot"]

REQUESTS_BATCH_SIZE = 200  # Number of input lines to process at once, must fit into memory
OUTPUT_FILE = "openai_api_response.jsonl"

# Azure endpoint constants
AZUREML_TOKEN_SCOPE = "https://ml.azure.com"
COGNITIVE_SERVICES_TOKEN_SCOPE = "https://cognitiveservices.azure.com/"
AZURE_TOKEN_REFRESH_INTERVAL = 600  # seconds
AZURE_ENDPOINT_DOMAIN_VALID_PATTERN_RE = (
    r"^(?=.{1,255}$)(?!-)[a-zA-Z0-9-]{1,63}(?<!-)"
    r"(\.(?!-)[a-zA-Z0-9-]{1,63}(?<!-))*\."
    r"(inference\.ml|openai)\.azure\.com$"
)
CHAT_START_TOKEN = "<|im_start|>"
CHAT_END_TOKEN = "<|im_end|>"


class ConversationRole(Enum):
    """Role in a chatbot conversation"""
    USER = "user"
    ASSISTANT = "assistant"
