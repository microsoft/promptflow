import os

from promptflow import tool
from promptflow.connections import CustomConnection


@tool
def print_secret(text: str, connection: CustomConnection):
    print(connection["key1"])
    print(connection["key2"])
    return text
