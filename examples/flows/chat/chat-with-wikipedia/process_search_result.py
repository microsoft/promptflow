from promptflow import tool


@tool
def process_search_result(search_result):
    def format(doc: dict):
        return f"Content: {doc['Content']}\nSource: {doc['Source']}"

    try:
        context = []
        for url, content in search_result:
            context.append({"Content": content, "Source": url})
        context_str = "\n\n".join([format(c) for c in context])
        return context_str
    except Exception as e:
        print(f"Error: {e}")
        return ""
