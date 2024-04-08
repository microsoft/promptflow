from promptflow.core import tool

@tool
def print_special_character(input1: str) -> str:
    # Add special character to test if file read is working.
    return "https://www.bing.com//"
