from promptflow import tool


@tool
def extract(result, search_engine):
    if search_engine == "Bing":
        return {
            "title": result["webPages"]["value"][0]["name"],
            "snippet": result["webPages"]["value"][0]["snippet"]}
    else:
        raise ValueError("search engine {} is not supported".format(search_engine))
