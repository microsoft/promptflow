import random
from promptflow import tool


@tool
def get_stock_price(symbol: str):
    """Get stock price for given symbol.
    
    :param symbol: stock ticker symbol
    :type symbol: str
    """

    return random.uniform(100, 400)
