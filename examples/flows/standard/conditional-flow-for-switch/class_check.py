from promptflow.core import tool


@tool
def class_check(llm_result: str) -> str:
    intentions_list = ["order_search", "product_info", "product_recommendation"]
    matches = [intention for intention in intentions_list if intention in llm_result.lower()]
    return matches[0] if matches else "unknown"
