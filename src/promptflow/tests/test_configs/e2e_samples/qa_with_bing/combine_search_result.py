from promptflow import tool


@tool
def combine_search_result(search_result):
    def format(doc: dict):
        return f"Content: {doc['Content']}\nSource: {doc['Source']}"

    try:
        context = []
        for data in search_result["webPages"]["value"]:
            context.append({
                # Truncate the content to 1024 characters to avoid token limit
                "Content": data.get("snippet", "")[:1024],
                "Source": data.get("url", "")
            })
        context_str = "\n\n".join([format(c) for c in context])
        return context_str
    except Exception as e:
        print("search result is not valid, error: {}".format(e))
        return ""
