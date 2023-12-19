from promptflow import tool

"""Auto-generated tool entry for @flow."""

from eager_mode_flow import my_flow

@tool
def entry(text: str):
    return my_flow(text=text)
