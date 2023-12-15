import os

from promptflow import tool
from promptflow.connections import CustomConnection


@tool
def my_python_tool(connection: CustomConnection):
    os.environ["AZURE_SEARCH_SERVICE_ENDPOINT"] = connection.configs["AZURE_SEARCH_SERVICE_ENDPOINT"]
    os.environ["AZURE_SEARCH_ADMIN_KEY"] = connection.secrets["AZURE_SEARCH_ADMIN_KEY"]
    os.environ["OPENAI_API_KEY"] = connection.secrets["OPENAI_API_KEY"]
    os.environ["OPENAI_API_TYPE"] = "azure"
    os.environ["OPENAI_ENDPOINT"] = connection.configs["OPENAI_ENDPOINT"]
    os.environ["OPENAI_API_VERSION"] = connection.configs["OPENAI_API_VERSION"]
    os.environ["AML_SUBSCRIPTION_ID"] = connection.secrets["AML_SUBSCRIPTION_ID"]
    os.environ["AML_RESOURCE_GROUP_NAME"] = connection.secrets["AML_RESOURCE_GROUP_NAME"]
    os.environ["AML_WORKSPACE_NAME"] = connection.secrets["AML_WORKSPACE_NAME"]

    if "AZURE_LANGUAGE_SERVICE_KEY" in connection.secrets:
        os.environ["AZURE_LANGUAGE_SERVICE_KEY"] = connection.secrets["AZURE_LANGUAGE_SERVICE_KEY"]

    if "AZURE_LANGUAGE_SERVICE_ENDPOINT" in connection.configs:
        os.environ["AZURE_LANGUAGE_SERVICE_ENDPOINT"] = connection.configs["AZURE_LANGUAGE_SERVICE_ENDPOINT"]

    if "LOGGING_LEVEL" in connection.configs:
        os.environ["LOGGING_LEVEL"] = connection.configs["LOGGING_LEVEL"]

    return True
