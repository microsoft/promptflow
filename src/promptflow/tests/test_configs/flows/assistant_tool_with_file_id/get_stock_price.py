from promptflow import tool


@tool
def get_stock_price():
    """Get the stock price for company C.
    """

    return [100, 105, 110, 115, 120, 125]
