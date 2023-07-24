from promptflow import tool
import requests
import bs4


@tool
def conditional_node(message: str):
    return message + "\nExecute the conditional_node"
