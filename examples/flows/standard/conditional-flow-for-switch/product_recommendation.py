from promptflow.core import tool


@tool
def product_recommendation(query: str) -> str:
    print(f"Your query is {query}.\nRecommending products...")
    return "I recommend promptflow to you, which can solve your problem very well."
