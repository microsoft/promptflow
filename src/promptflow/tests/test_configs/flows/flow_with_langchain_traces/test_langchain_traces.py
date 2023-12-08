import os

from langchain.chat_models import AzureChatOpenAI
from langchain_core.messages import HumanMessage, BaseMessage

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection


@tool
def test_langchain_traces(question: str, conn: AzureOpenAIConnection):
    os.environ["AZURE_OPENAI_API_KEY"] = conn.api_key
    os.environ["OPENAI_API_VERSION"] = conn.api_version
    os.environ["AZURE_OPENAI_ENDPOINT"] = conn.api_base

    model = AzureChatOpenAI(
        temperature=0.7,
        azure_deployment="gpt-35-turbo",
    )

    message = HumanMessage(
        content=question
    )

    res = model([message])
    return res.content
