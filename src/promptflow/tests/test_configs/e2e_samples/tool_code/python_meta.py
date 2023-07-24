from typing import Union

from promptflow import tool
from promptflow.connections import BingConnection, CustomConnection

#  Add the following line to make sure we could import builtin tools
from promptflow.tools.bing import search


@tool
def extract(result, search_engine: str, bing_conn: Union[BingConnection, CustomConnection]):
    search(bing_conn, "query")
    if search_engine == "Bing":
        return {"title": result["webPages"]["value"][0]["name"], "snippet": result["webPages"]["value"][0]["snippet"]}
    else:
        raise ValueError("search engine {} is not supported".format(search_engine))
