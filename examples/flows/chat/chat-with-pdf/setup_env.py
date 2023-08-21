import os

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection

from chat_with_pdf.utils.lock import acquire_lock


@tool
def setup_env(aoai_connection: AzureOpenAIConnection, config: dict):
    if not aoai_connection or not config:
        return
    os.environ["OPENAI_API_BASE"] = aoai_connection.api_base
    os.environ["OPENAI_API_KEY"] = aoai_connection.api_key
    os.environ["OPENAI_API_VERSION"] = aoai_connection.api_version
    for key in config:
        os.environ[key] = str(config[key])

    with acquire_lock("create_folder.lock"):
        if not os.path.exists(".pdfs"):
            os.mkdir(".pdfs")
        if not os.path.exists(".index/.pdfs"):
            os.makedirs(".index/.pdfs")

    return "Ready"
