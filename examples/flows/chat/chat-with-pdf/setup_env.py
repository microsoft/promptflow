import os
from typing import Union

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection, OpenAIConnection

from chat_with_pdf.utils.lock import acquire_lock

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) + "/chat_with_pdf/"


@tool
def setup_env(connection: Union[AzureOpenAIConnection, OpenAIConnection], config: dict):
    if not connection or not config:
        return

    if isinstance(connection, AzureOpenAIConnection):
        os.environ["OPENAI_API_TYPE"] = "azure"
        os.environ["OPENAI_API_BASE"] = connection.api_base
        os.environ["OPENAI_API_KEY"] = connection.api_key
        os.environ["OPENAI_API_VERSION"] = connection.api_version

    if isinstance(connection, OpenAIConnection):
        os.environ["OPENAI_API_KEY"] = connection.api_key
        if connection.organization is not None:
            os.environ["OPENAI_ORG_ID"] = connection.organization

    for key in config:
        os.environ[key] = str(config[key])

    with acquire_lock(BASE_DIR + "create_folder.lock"):
        if not os.path.exists(BASE_DIR + ".pdfs"):
            os.mkdir(BASE_DIR + ".pdfs")
        if not os.path.exists(BASE_DIR + ".index/.pdfs"):
            os.makedirs(BASE_DIR + ".index/.pdfs")

    return "Ready"
