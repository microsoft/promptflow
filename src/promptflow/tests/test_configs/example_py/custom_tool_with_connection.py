from promptflow import tool

# Not supported for now
# from promptflow.tools.bing import Bing as NewBing
# from promptflow.tools.bing import search as new_search
from promptflow.connections import AzureOpenAIConnection
from promptflow.connections import BingConnection as BingConn

# Test different type function source
from promptflow.tools.aoai import AzureOpenAI, completion


def do_nothing():
    assert completion


@tool
def consume_connection(
    question: str, aoai: AzureOpenAIConnection, bing: BingConn
):
    do_nothing()
    assert isinstance(aoai, AzureOpenAIConnection)
    assert isinstance(bing, BingConn)
    return AzureOpenAI(aoai).completion(question, "text-ada-001")
