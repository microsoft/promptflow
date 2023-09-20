from promptflow import tool


@tool
def generate_response(order_search="", product_info="", product_recommendation="") -> str:
    default_response = "Sorry, no results matching your search were found."
    responses = [order_search, product_info, product_recommendation]
    return next((response for response in responses if response), default_response)
