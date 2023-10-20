from promptflow import tool


@tool
def product_info(query: str) -> str:
    print(f"Your query is {query}.\nLooking for product information...")
    return "This product is produced by Microsoft."
