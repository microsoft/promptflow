from promptflow.core import tool


@tool
def order_search(query: str) -> str:
    print(f"Your query is {query}.\nSearching for order...")
    return "Your order is being mailed, please wait patiently."
