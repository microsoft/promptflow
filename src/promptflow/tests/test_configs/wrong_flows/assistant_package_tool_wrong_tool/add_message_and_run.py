from typing import Union

from promptflow.core import tool
from promptflow.connections import OpenAIConnection, AzureOpenAIConnection
from promptflow.contracts.types import AssistantDefinition

URL_PREFIX = "https://platform.openai.com/files/"
RUN_STATUS_POLLING_INTERVAL_IN_MILSEC = 1000


@tool
async def add_message_and_run(
        conn: Union[AzureOpenAIConnection, OpenAIConnection],
        assistant_id: str,
        thread_id: str,
        message: list,
        assistant_definition: AssistantDefinition,
        download_images: bool,
):
    pass