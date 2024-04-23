from enum import Enum

from promptflow import tool
from promptflow.connections import AzureOpenAIConnection

class Unit(Enum):
    c = 'c'
    f = 'f'

class Person:
    def __init__(self, name):
        """Initializer for the Person class."""
        self.name = name  # A member variable to store the person's name

    def greet(self):
        """A member method that prints a greeting."""
        print(f"Hello, my name is {self.name}.")


@tool
def echo(connection: AzureOpenAIConnection,
         message_str: str,
         message_float: float,
         message_int: int,
         message_bool: bool,
         message_list: list,
         message_dict: dict,
         message_none: None,
         message_enum_str: Unit,
         message_custom_type: Person,
         message_no_type,
         message_default=2
         ):
    """This tool is used to echo the message back.
    """
    assert isinstance(connection, AzureOpenAIConnection)
    return "hello world"

