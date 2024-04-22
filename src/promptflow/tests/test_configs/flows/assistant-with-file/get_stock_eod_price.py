import random
import time

from promptflow.core import tool


@tool
def get_stock_eod_price(date: str, company: str):
    """Get the stock end of day price by date and symbol.

    :param date: the date of the stock price. e.g. 2021-01-01
    :type date: str
    :param company: the company name like A, B, C
    :type company: str
    """
    print(f"Try to get the stock end of day price by date {date} and company {company}.")

    # Sleep a random number between 0.2s and 1s for tracing purpose
    time.sleep(random.uniform(0.2, 1))

    return random.uniform(110, 130)
