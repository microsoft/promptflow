from time import sleep
from promptflow.core import tool
from promptflow.tracing import trace


@trace
def is_valid_name(name):
    sleep(0.5)
    return len(name) > 0


@trace
def get_user_name(user_id):
    sleep(0.5)
    user_name = f"User {user_id}"
    if not is_valid_name(user_name):
        raise ValueError(f"Invalid user name: {user_name}")

    return user_name


@trace
def format_greeting(user_name):
    sleep(0.5)
    return f"Hello, {user_name}!"


@tool
def greetings(user_id):
    user_name = get_user_name(user_id)
    greeting = format_greeting(user_name)
    print(greeting)
    return {"greeting": greeting}
